import math
from statistics import NormalDist, mean, pstdev
from datetime import date, timedelta
from sqlalchemy import select, func
from fastapi import HTTPException
from .models import *
from .security import audit

def record(db, cls, ident):
    obj = db.get(cls, ident)
    if obj is None:
        raise HTTPException(404, f'{cls.__name__} not found')
    return obj

def serialize(obj):
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns if c.name != 'password_hash'}

def supplier_performance(db, supplier_id):
    cache=db.info.get('analysis_supplier_performance',{})
    if supplier_id in cache:
        return cache[supplier_id]
    supplier = record(db, Supplier, supplier_id)
    deliveries = db.scalars(select(Delivery).where(Delivery.supplier_id==supplier_id)).all()
    rate = sum(d.actual_days<=d.promised_days for d in deliveries)/len(deliveries) if deliveries else None
    return {**serialize(supplier), 'delivery_count':len(deliveries),'on_time_rate':rate,'mean_actual_days':mean([d.actual_days for d in deliveries]) if deliveries else None}

def compare_suppliers(db, product_id):
    cache=db.info.get('analysis_offers',{})
    offers = cache[product_id] if product_id in cache else db.scalars(select(SupplierProduct).where(SupplierProduct.product_id==product_id)).all()
    results = []
    for offer in offers:
        perf = supplier_performance(db, offer.supplier_id)
        results.append({**serialize(offer),'supplier_name':perf['name'],'on_time_rate':perf['on_time_rate'], 'score':round(100*(.4*min(o.unit_price for o in offers)/offer.unit_price+.3*min(o.lead_days for o in offers)/offer.lead_days+.3*(perf['on_time_rate'] or 0)),2)})
    return sorted(results,key=lambda r:r['score'], reverse=True)

def inventory(db, product_id=None):
    cached=db.info.get('analysis_inventory')
    if cached is not None:
        return [r for r in cached if r['id']==product_id] if product_id else cached
    if db.info.get('analysis_snapshot'):
        # Fetch a consistent workflow snapshot in bounded queries, rather than
        # repeating product/supplier/stock queries in every agent node.
        products=db.scalars(select(Product)).all()
        ids=[p.id for p in products]
        stocks={pid:[] for pid in ids}; sales={pid:[] for pid in ids}; offers={pid:[] for pid in ids}
        for row in db.scalars(select(Inventory).where(Inventory.product_id.in_(ids))).all(): stocks[row.product_id].append(row)
        ranked=select(Sale.id,func.row_number().over(partition_by=Sale.product_id,order_by=Sale.date.desc()).label('position')).where(Sale.product_id.in_(ids)).subquery()
        for row in db.scalars(select(Sale).join(ranked,Sale.id==ranked.c.id).where(ranked.c.position<=60).order_by(Sale.date.desc())).all(): sales[row.product_id].append(row)
        for row in db.scalars(select(SupplierProduct).where(SupplierProduct.product_id.in_(ids))).all(): offers[row.product_id].append(row)
        supplier_ids={o.supplier_id for rows in offers.values() for o in rows}
        supplier_rows=db.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids))).all()
        deliveries={s.id:[] for s in supplier_rows}
        for row in db.scalars(select(Delivery).where(Delivery.supplier_id.in_(supplier_ids))).all(): deliveries[row.supplier_id].append(row)
        db.info['analysis_supplier_performance']={s.id:{**serialize(s),'delivery_count':len(deliveries[s.id]),'on_time_rate':sum(d.actual_days<=d.promised_days for d in deliveries[s.id])/len(deliveries[s.id]) if deliveries[s.id] else None,'mean_actual_days':mean([d.actual_days for d in deliveries[s.id]]) if deliveries[s.id] else None} for s in supplier_rows}
        db.info['analysis_offers']=offers
        db.info['analysis_sales']=sales
        incoming=dict(db.execute(select(PurchaseOrder.product_id,func.sum(PurchaseOrder.quantity)).where(PurchaseOrder.status=='approved',PurchaseOrder.product_id.in_(ids)).group_by(PurchaseOrder.product_id)).all())
        result=[]
        for p in products:
            daily=mean([s.quantity for s in sales[p.id]]) if sales[p.id] else 0
            ranked_offers=compare_suppliers(db,p.id)
            lead=ranked_offers[0]['lead_days'] if ranked_offers else 7
            qty=sum(s.quantity for s in stocks[p.id]); days=qty/daily if daily else None
            status='stockout' if qty==0 else 'low' if daily and qty<daily*lead else 'overstock' if daily and qty>daily*90 else 'healthy'
            result.append({**serialize(p),'quantity':qty,'incoming':incoming.get(p.id,0),'daily_demand':round(daily,2),'days_cover':round(days,1) if days is not None else None,'value':round(qty*p.price,2),'status':status,'batches':[serialize(s) for s in stocks[p.id]]})
        db.info['analysis_inventory']=result
        return [r for r in result if r['id']==product_id] if product_id else result
    products = db.scalars(select(Product).where(Product.id==product_id) if product_id else select(Product)).all()
    result=[]
    for p in products:
        stocks=db.scalars(select(Inventory).where(Inventory.product_id==p.id)).all()
        sales=db.scalars(select(Sale).where(Sale.product_id==p.id).order_by(Sale.date.desc()).limit(60)).all()
        daily=mean([s.quantity for s in sales]) if sales else 0
        offers=compare_suppliers(db,p.id)
        lead=offers[0]['lead_days'] if offers else 7
        qty=sum(s.quantity for s in stocks)
        days=qty/daily if daily else None
        status='stockout' if qty==0 else 'low' if daily and qty<daily*lead else 'overstock' if daily and qty>daily*90 else 'healthy'
        incoming=db.scalar(select(func.coalesce(func.sum(PurchaseOrder.quantity),0)).where(PurchaseOrder.product_id==p.id,PurchaseOrder.status=='approved'))
        result.append({**serialize(p),'quantity':qty,'incoming':incoming,'daily_demand':round(daily,2),'days_cover':round(days,1) if days is not None else None,'value':round(qty*p.price,2),'status':status,'batches':[serialize(s) for s in stocks]})
    return result

def replenishment(db, product_id, budget=25000, service_level=.95, demand_forecast=None):
    p=record(db,Product,product_id)
    inv=inventory(db,product_id)[0]
    offers=compare_suppliers(db,product_id)
    if not offers:
        return {'product_id':product_id,'feasible':False,'reason':'No supplier offers available','quantity':0}
    supplier=offers[0]
    sales=[r.quantity for r in db.info['analysis_sales'][product_id]] if product_id in db.info.get('analysis_sales',{}) else db.scalars(select(Sale.quantity).where(Sale.product_id==product_id).order_by(Sale.date.desc()).limit(60)).all()
    historical=mean(sales) if sales else 0
    daily=demand_forecast['total_demand']/demand_forecast['horizon'] if demand_forecast else historical
    sigma=pstdev(sales) if len(sales)>1 else 0
    lead=supplier['lead_days']
    z=NormalDist().inv_cdf(service_level)
    safety=z*math.sqrt(lead*sigma*sigma+daily*daily*supplier['lead_std']**2)
    rop=daily*lead+safety
    target=daily*(lead+30)+safety
    net=max(0,math.ceil(target-inv['quantity']-inv['incoming']))
    eoq=math.sqrt(2*daily*365*p.ordering_cost/p.holding_cost) if daily else 0
    need=inv['quantity']+inv['incoming']<=rop
    options=[]
    for offer in offers:
        # Reserve capacity for on-hand plus all already-approved receipts.
        cap=max(0,min(p.capacity-inv['quantity']-inv['incoming'],offer['available'],math.floor(budget/offer['unit_price'])))
        lower=math.ceil(offer['moq']/offer['pack_size'])*offer['pack_size']
        demand=daily*(offer['lead_days']+30)
        upper=math.floor(cap/offer['pack_size'])*offer['pack_size']
        # Piecewise-linear cost can attain its minimum only at an endpoint or
        # adjacent pack multiple around a holding/shortage breakpoint.
        breakpoints=[lower,upper,demand+safety-inv['quantity']-inv['incoming'],demand/2-inv['quantity']-inv['incoming']]
        quantities={int(rounding(q/offer['pack_size'])*offer['pack_size']) for q in breakpoints for rounding in (math.floor,math.ceil)}
        for quantity in sorted(q for q in quantities if lower<=q<=upper):
            shortage=max(0,demand+safety-inv['quantity']-inv['incoming']-quantity)
            avg_stock=max(0,(inv['quantity']+inv['incoming']+quantity-demand/2))
            holding=avg_stock*p.holding_cost*30/365
            stockout=shortage*p.stockout_cost
            purchase=quantity*offer['unit_price']
            cost=purchase+p.ordering_cost+holding+stockout
            options.append({'quantity':quantity,'supplier_id':offer['supplier_id'],'supplier_name':offer['supplier_name'],'unit_price':offer['unit_price'],'lead_days':offer['lead_days'],'total_cost':round(cost,2),'purchase_cost':round(purchase,2),'holding_cost':round(holding,2),'ordering_cost':p.ordering_cost,'stockout_cost':round(stockout,2),'expected_shortage':round(shortage,2)})
    best=min(options,key=lambda o:o['total_cost']) if options and need else None
    result={'product_id':product_id,'sku':p.sku,'name':p.name,'available':inv['quantity'],'incoming':inv['incoming'],'daily_demand':round(daily,2),'demand_source':'selected forecast' if demand_forecast else '60-day historical mean','lead_days':lead,'safety_stock':round(safety,2),'reorder_point':round(rop,2),'target_stock':round(target,2),'net_requirement':net,'eoq':round(eoq,2),'needs_reorder':need,'quantity':best['quantity'] if best else 0,'feasible':bool(best) if need else True,'reason':'Feasible candidate with lowest purchase + ordering + 30-day holding + shortage penalty cost' if best else 'No feasible MOQ/pack combination within capacity, supplier availability and budget' if need else 'Inventory position exceeds reorder point','solution':best,'candidate_count':len(options),'budget':budget,'service_level':service_level,'priority':'critical' if inv['quantity']==0 else 'high' if need else 'normal','estimated_stockout_date':(date.today()+timedelta(days=int(inv['days_cover']))).isoformat() if inv['days_cover'] is not None else None,'assumptions':'Independent daily demand and lead time; safety stock = z sqrt(L sigma_d² + mean_d² sigma_L²). Costs in USD; holding cost per unit/year. Candidate enumeration is a per-product heuristic, not a portfolio optimizer. Supplier lead variability comes from configured offer estimates.'}
    if best and best['expected_shortage']>0:
        result['reason']+=f". Residual expected shortage: {best['expected_shortage']} units; the configured shortage penalty can favor a smaller order. Review costs and service risk before drafting."
    return result

def draft_order(db,user,product_id,supplier_id,quantity):
    p=record(db,Product,product_id)
    offer=db.scalar(select(SupplierProduct).where(SupplierProduct.product_id==product_id,SupplierProduct.supplier_id==supplier_id))
    if not offer or quantity<offer.moq or quantity%offer.pack_size or quantity>offer.available:
        raise HTTPException(422,'Order violates supplier MOQ, pack size or availability')
    inv=inventory(db,product_id)[0]
    if quantity+inv['quantity']+inv['incoming']>p.capacity:
        raise HTTPException(422,'Insufficient warehouse capacity including confirmed incoming stock')
    po=PurchaseOrder(product_id=product_id,supplier_id=supplier_id,quantity=quantity,unit_price=offer.unit_price,requested_by=user.id)
    db.add(po)
    db.flush()
    audit(db,user,'purchase_order.drafted',{'order_id':po.id,'quantity':quantity})
    return serialize(po)

def alerts(db):
    output=[]
    for item in inventory(db):
        if item['status']!='healthy':
            output.append({'product_id':item['id'],'name':item['name'],'category':item['status'],'risk_score':100 if item['status']=='stockout' else 75 if item['status']=='low' else 50,'evidence':f"{item['quantity']} units; {item['days_cover']} days cover",'mitigation':'Review replenishment plan' if item['status']!='overstock' else 'Reduce replenishment and review transfers'})
        for batch in item['batches']:
            if batch['expiry'] and batch['quantity'] and batch['expiry'] <= (date.today()+timedelta(days=30)).isoformat():
                output.append({'product_id':item['id'],'name':item['name'],'category':'expiry','risk_score':80,'evidence':f"Batch {batch['batch']} expires {batch['expiry']}",'mitigation':'Prioritize FEFO allocation'})
        recent=[r.quantity for r in db.info['analysis_sales'][item['id']][:35]] if item['id'] in db.info.get('analysis_sales',{}) else db.scalars(select(Sale.quantity).where(Sale.product_id==item['id']).order_by(Sale.date.desc()).limit(35)).all()
        if len(recent)==35:
            baseline=mean(recent[7:]); observed=mean(recent[:7]); spread=pstdev(recent[7:])
            if spread and abs(observed-baseline)>3*spread/math.sqrt(7):
                output.append({'product_id':item['id'],'name':item['name'],'category':'demand anomaly','risk_score':min(100,round(abs(observed-baseline)/spread*25)),'evidence':f'Last 7-day mean {observed:.2f} vs prior 28-day mean {baseline:.2f}; prior daily std {spread:.2f}','mitigation':'Review promotions, data quality and forecast assumptions; heuristic signal, not a calibrated probability'})
    for s in db.scalars(select(Supplier)).all():
        perf=supplier_performance(db,s.id)
        if perf['on_time_rate'] is not None and perf['on_time_rate']<.8:
            output.append({'supplier_id':s.id,'name':s.name,'category':'supplier delay','risk_score':round((1-perf['on_time_rate'])*100),'evidence':f"{perf['delivery_count']} deliveries; {perf['on_time_rate']:.0%} on-time",'mitigation':'Review alternate suppliers and lead-time buffer'})
    return output
