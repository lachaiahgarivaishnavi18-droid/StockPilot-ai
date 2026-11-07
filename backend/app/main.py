import os
import json
import time
import logging
import secrets
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update, text
from sqlalchemy.exc import IntegrityError
from .database import Base, engine, get_db, now
from .models import *
from .schemas import *
from .security import current_user, require, audit, passwords, token
from .services import *
from .forecasting import forecast
from .agents import run_workflow, assistant, AGENTS
from .tools import REGISTRY
from .imports import parse, commit_import
from .seed import seed

@asynccontextmanager
async def lifespan(app):
    if os.getenv('APP_ENV')!='production': Base.metadata.create_all(engine)
    yield

app=FastAPI(title='StockPilot AI',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','),allow_methods=['GET','POST','PUT'],allow_headers=['Authorization','Content-Type'])
requests=defaultdict(deque)
@app.middleware('http')
async def limit(request:Request,call_next):
    key=request.client.host if request.client else 'unknown'
    bucket=requests[key]; timestamp=time.monotonic()
    while bucket and timestamp-bucket[0]>60: bucket.popleft()
    if len(bucket)>=180: return JSONResponse({'detail':'Rate limit exceeded; retry in one minute'},status_code=429)
    bucket.append(timestamp)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(IntegrityError)
async def integrity(request,exc): return JSONResponse({'detail':'Duplicate record or invalid relation'},status_code=409)

@app.get('/api/health')
def health(): return {'status':'ok','data_mode':'User imports or explicitly loaded synthetic demonstration data','supplier_transmission':False}

@app.post('/api/auth/register',status_code=201)
def register(body:Credentials,db=Depends(get_db)):
    # No public account can acquire approval permissions.
    user=User(email=body.email.lower(),name=body.name,password_hash=passwords.hash(body.password),role='analyst')
    db.add(user); db.commit()
    return {'access_token':token(user),'user':serialize(user)}

@app.post('/api/auth/login')
def login(body:Credentials,db=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==body.email.lower()))
    if not user or not passwords.verify(body.password,user.password_hash): raise HTTPException(401,'Invalid credentials')
    return {'access_token':token(user),'user':serialize(user)}

@app.post('/api/auth/bootstrap',status_code=201)
def bootstrap_admin(body:BootstrapCredentials,db=Depends(get_db)):
    expected=os.getenv('BOOTSTRAP_TOKEN','')
    if not expected or not secrets.compare_digest(expected,body.setup_token):
        raise HTTPException(403,'Invalid administrator setup link')
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(87321045)'))
    if db.scalar(select(User.id).where(User.role=='admin').limit(1)):
        raise HTTPException(409,'Administrator setup is already complete. Sign in with your account.')
    user=User(email=body.email.lower(),name=body.name,password_hash=passwords.hash(body.password),role='admin')
    db.add(user); db.flush(); audit(db,user,'administrator.initialized',{}); db.commit()
    return {'access_token':token(user),'user':serialize(user)}

@app.get('/api/auth/me')
def me(user=Depends(current_user)): return serialize(user)

@app.post('/api/demo/load')
def load(user=Depends(current_user),db=Depends(get_db)):
    require(user)
    result=seed(db); audit(db,user,'demo.loaded',result); db.commit(); return result

@app.get('/api/products')
def products(search:str='',page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),user=Depends(current_user),db=Depends(get_db)):
    query=select(Product).where(Product.name.ilike(f'%{search}%')|Product.sku.ilike(f'%{search}%')).order_by(Product.id)
    allrows=db.scalars(query).all()
    return {'items':[serialize(p) for p in allrows[(page-1)*page_size:page*page_size]],'total':len(allrows),'page':page}

@app.get('/api/products/{product_id}')
def product(product_id:int,user=Depends(current_user),db=Depends(get_db)): return serialize(record(db,Product,product_id))

@app.post('/api/products',status_code=201)
def create_product(body:ProductInput,user=Depends(current_user),db=Depends(get_db)):
    require(user,('admin','approver','planner')); p=Product(**body.model_dump()); db.add(p); db.flush(); audit(db,user,'product.created',{'id':p.id}); db.commit(); return serialize(p)

@app.put('/api/products/{product_id}')
def edit_product(product_id:int,body:ProductInput,user=Depends(current_user),db=Depends(get_db)):
    require(user); p=record(db,Product,product_id)
    for k,v in body.model_dump().items(): setattr(p,k,v)
    audit(db,user,'product.updated',{'id':p.id}); db.commit(); return serialize(p)

@app.get('/api/inventory')
def get_inventory(user=Depends(current_user),db=Depends(get_db)): return inventory(db)

@app.get('/api/inventory/low-stock')
def low(user=Depends(current_user),db=Depends(get_db)): return [r for r in inventory(db) if r['status'] in ('low','stockout')]

@app.get('/api/inventory/stockout-risk')
def risk(user=Depends(current_user),db=Depends(get_db)): return alerts(db)

@app.get('/api/inventory/movements')
def movements(user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(Movement).order_by(Movement.id.desc()).limit(500)).all()]

@app.post('/api/inventory/movements')
def move(body:MovementArgs,user=Depends(current_user),db=Depends(get_db)):
    require(user); p=record(db,Product,body.product_id); record(db,Warehouse,body.warehouse_id)
    stock=db.scalar(select(Inventory).where(Inventory.product_id==p.id,Inventory.warehouse_id==body.warehouse_id))
    if not stock: stock=Inventory(product_id=p.id,warehouse_id=body.warehouse_id,quantity=0); db.add(stock); db.flush()
    if not 0<=stock.quantity+body.quantity<=p.capacity: raise HTTPException(422,'Stock adjustment exceeds capacity or available stock')
    stock.quantity+=body.quantity
    db.add(Movement(**body.model_dump(exclude={'confirm'}),user_id=user.id)); audit(db,user,'inventory.adjusted',body.model_dump()); db.commit(); return serialize(stock)

@app.get('/api/warehouses')
def warehouses(user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(Warehouse)).all()]

@app.get('/api/sales')
def sales(page:int=Query(1,ge=1),user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(Sale).order_by(Sale.date.desc()).offset((page-1)*100).limit(100)).all()]

@app.get('/api/sales/history/{product_id}')
def history(product_id:int,user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(Sale).where(Sale.product_id==product_id).order_by(Sale.date)).all()]

@app.post('/api/sales',status_code=201)
def add_sale(body:SaleArgs,user=Depends(current_user),db=Depends(get_db)):
    require(user,('admin','approver','planner')); record(db,Product,body.product_id); date.fromisoformat(body.date)
    row=Sale(**body.model_dump()); db.add(row); audit(db,user,'sales.created',body.model_dump()); db.commit(); return serialize(row)

@app.post('/api/forecast/generate')
def generate(body:ForecastArgs,user=Depends(current_user),db=Depends(get_db)):
    result=forecast(db,**body.model_dump()); db.commit(); return result

@app.get('/api/forecast/evaluation')
def evaluations(user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(StoredResult).where(StoredResult.kind=='forecast').order_by(StoredResult.id.desc()).limit(50)).all()]

@app.get('/api/forecast/{product_id}')
def get_forecast(product_id:int,user=Depends(current_user),db=Depends(get_db)):
    row=db.scalar(select(StoredResult).where(StoredResult.kind=='forecast',StoredResult.product_id==product_id).order_by(StoredResult.id.desc()).limit(1))
    if not row: raise HTTPException(404,'Generate a forecast first')
    return row.data

@app.get('/api/replenishment/recommendations')
def recommendations(user=Depends(current_user),db=Depends(get_db)): return [replenishment(db,p.id) for p in db.scalars(select(Product)).all()]

@app.post('/api/replenishment/calculate')
@app.post('/api/replenishment/optimize')
def optimize(body:OptimizeArgs,user=Depends(current_user),db=Depends(get_db)):
    result=replenishment(db,**body.model_dump()); db.add(StoredResult(kind='optimization',product_id=body.product_id,data=result)); db.commit(); return result

@app.get('/api/suppliers/compare')
def compare(product_id:int,user=Depends(current_user),db=Depends(get_db)): return compare_suppliers(db,product_id)

@app.get('/api/suppliers')
def suppliers(user=Depends(current_user),db=Depends(get_db)): return [supplier_performance(db,s.id) for s in db.scalars(select(Supplier)).all()]

@app.get('/api/suppliers/{supplier_id}')
def supplier(supplier_id:int,user=Depends(current_user),db=Depends(get_db)): return supplier_performance(db,supplier_id)

@app.get('/api/purchase-orders')
def orders(user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.id.desc())).all()]

@app.get('/api/purchase-orders/{order_id}')
def order(order_id:int,user=Depends(current_user),db=Depends(get_db)): return serialize(record(db,PurchaseOrder,order_id))

@app.post('/api/purchase-orders/draft',status_code=201)
def draft(body:DraftArgs,user=Depends(current_user),db=Depends(get_db)):
    require(user,('admin','approver','planner')); result=draft_order(db,user,**body.model_dump()); db.commit(); return result

@app.post('/api/purchase-orders/{order_id}/approve')
def approve(order_id:int,user=Depends(current_user),db=Depends(get_db)):
    require(user); po=record(db,PurchaseOrder,order_id)
    if po.status!='draft': raise HTTPException(409,'Only draft orders can be approved')
    p=record(db,Product,po.product_id); inv=inventory(db,p.id)[0]
    offer=db.scalar(select(SupplierProduct).where(SupplierProduct.product_id==p.id,SupplierProduct.supplier_id==po.supplier_id))
    if not offer or po.quantity>offer.available or po.quantity<offer.moq or po.quantity%offer.pack_size: raise HTTPException(422,'Supplier terms or availability changed; create a new draft')
    if inv['quantity']+inv['incoming']+po.quantity>p.capacity: raise HTTPException(422,'Capacity changed; review the draft')
    result=db.execute(update(PurchaseOrder).where(PurchaseOrder.id==po.id,PurchaseOrder.status=='draft').values(status='approved',approved_by=user.id,approved_at=now()))
    if result.rowcount!=1: raise HTTPException(409,'Order was already reviewed')
    offer.available-=po.quantity
    audit(db,user,'purchase_order.approved',{'order_id':po.id,'total':po.quantity*po.unit_price,'supplier_transmitted':False}); db.commit(); db.refresh(po); return serialize(po)

@app.get('/api/agents')
def agents(user=Depends(current_user)): return {'agents':AGENTS,'tools':[{'name':n,'kind':k,'schema':s.model_json_schema()} for n,(s,k) in REGISTRY.items()],'checkpointing':'Per-run in-memory LangGraph checkpoints; final state persisted in database. Cross-process resume is not supported.'}

@app.post('/api/agents/run')
def run(body:RunArgs,user=Depends(current_user),db=Depends(get_db)): return run_workflow(db,user,**body.model_dump())

@app.get('/api/agents/executions')
def executions(user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(Execution).order_by(Execution.id.desc()).limit(100)).all()]

@app.get('/api/agents/executions/{execution_id}')
def execution(execution_id:int,user=Depends(current_user),db=Depends(get_db)): return {'execution':serialize(record(db,Execution,execution_id)),'calls':[serialize(r) for r in db.scalars(select(ToolCall).where(ToolCall.execution_id==execution_id)).all()]}

@app.post('/api/assistant/query')
def query(body:QueryArgs,user=Depends(current_user),db=Depends(get_db)):
    result=assistant(db,user,**body.model_dump()); db.commit(); return result

@app.post('/api/import')
async def upload(file:UploadFile=File(...),kind:str=Form(...),mapping:str=Form('{}'),preview:bool=Form(True),confirm:bool=Form(False),user=Depends(current_user),db=Depends(get_db)):
    if kind not in ('products','sales','inventory'): raise HTTPException(422,'Unsupported dataset kind')
    try: column_map=json.loads(mapping)
    except ValueError: raise HTTPException(422,'Mapping must be JSON')
    if not isinstance(column_map,dict): raise HTTPException(422,'Mapping must be an object')
    content=await file.read(2*1024*1024+1)
    parsed=parse(content,file.filename or '',kind,column_map)
    if preview: return {**parsed,'rows':parsed['rows'][:20]}
    return commit_import(db,user,parsed,file.filename or '',confirm)

@app.get('/api/imports')
def imports(user=Depends(current_user),db=Depends(get_db)): return [serialize(r) for r in db.scalars(select(ImportRecord).order_by(ImportRecord.id.desc())).all()]

@app.get('/api/reports')
def reports(user=Depends(current_user),db=Depends(get_db)):
    inv=inventory(db); pos=db.scalars(select(PurchaseOrder)).all()
    return {'generated_at':now(),'inventory':inv,'alerts':alerts(db),'purchase_orders':[serialize(p) for p in pos],'suppliers':[supplier_performance(db,s.id) for s in db.scalars(select(Supplier)).all()],'summary':{'total_products':len(inv),'inventory_value':round(sum(r['value'] for r in inv),2),'low_stock':sum(r['status']=='low' for r in inv),'stockout':sum(r['status']=='stockout' for r in inv),'overstock':sum(r['status']=='overstock' for r in inv),'pending_orders':sum(p.status=='draft' for p in pos),'approved_commitment':round(sum(p.quantity*p.unit_price for p in pos if p.status=='approved'),2)}}

@app.get('/api/analytics/summary')
def analytics_summary(user=Depends(current_user),db=Depends(get_db)):
    latest={}
    for row in db.scalars(select(StoredResult).where(StoredResult.kind=='forecast').order_by(StoredResult.id)).all():
        latest[row.product_id]=row.data
    recommendations=[replenishment(db,p.id) for p in db.scalars(select(Product)).all()]
    return {'forecasted_demand':round(sum(f['total_demand'] for f in latest.values()),2),'forecasted_products':len(latest),'replenishment_recommendations':sum(r.get('needs_reorder',False) for r in recommendations),'recommendations':recommendations}

@app.post('/api/reports/generate')
def generate_report(user=Depends(current_user),db=Depends(get_db)):
    result=reports(user,db); db.add(StoredResult(kind='report',data=result)); audit(db,user,'report.generated',{}); db.commit(); return result

@app.get('/api/audit')
def logs(user=Depends(current_user),db=Depends(get_db)):
    require(user); return [serialize(r) for r in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(500)).all()]

@app.get('/api/users')
def users(user=Depends(current_user),db=Depends(get_db)):
    require(user); return [serialize(r) for r in db.scalars(select(User)).all()]

@app.get('/api/settings')
def settings(user=Depends(current_user)):
    return {'environment':os.getenv('APP_ENV','development'),'database':'PostgreSQL' if engine.dialect.name=='postgresql' else 'SQLite','llm_configured':bool(os.getenv('OPENAI_API_KEY')),'supplier_transmission':False,'service_level':.95,'currency':'USD','demo_note':'Sample data is synthetic; imported records remain user-provided. All approval actions are local only.'}
