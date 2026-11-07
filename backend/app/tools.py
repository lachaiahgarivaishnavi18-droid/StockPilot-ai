import time
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from fastapi import HTTPException
from .schemas import ProductArgs, ForecastArgs, OptimizeArgs, DraftArgs, OrderArgs
from .models import Product, Sale, Supplier, PurchaseOrder, ToolCall
from .services import inventory, record, serialize, compare_suppliers, supplier_performance, replenishment, draft_order, alerts
from .forecasting import forecast

class Empty(BaseModel):
    model_config = ConfigDict(extra='forbid')

REGISTRY = {
    'get_inventory':(ProductArgs,'read'),
    'get_product_details':(ProductArgs,'read'),
    'get_sales_history':(ProductArgs,'read'),
    'get_supplier_details':(ProductArgs,'read'),
    'get_supplier_performance':(ProductArgs,'read'),
    'generate_demand_forecast':(ForecastArgs,'analytical'),
    'calculate_reorder_point':(ProductArgs,'analytical'),
    'calculate_safety_stock':(ProductArgs,'analytical'),
    'calculate_order_quantity':(ProductArgs,'analytical'),
    'compare_suppliers':(ProductArgs,'analytical'),
    'optimize_replenishment':(OptimizeArgs,'analytical'),
    'create_purchase_order_draft':(DraftArgs,'draft'),
    'validate_purchase_order':(OrderArgs,'read'),
    'get_inventory_alerts':(Empty,'read'),
    'generate_inventory_report':(Empty,'read'),
}

def execute(db,user,name,arguments,execution_id=None,allow_draft=False):
    started=time.monotonic()
    result={}
    status='failed'
    try:
        if name not in REGISTRY:
            raise HTTPException(422,'Unknown tool')
        schema,kind=REGISTRY[name]
        args=schema.model_validate(arguments).model_dump()
        if kind=='draft' and (not allow_draft or user.role not in ('admin','approver','planner')):
            raise HTTPException(403,'Draft creation requires a planner and explicit draft intent')
        pid=args.get('product_id')
        if pid:
            record(db,Product,pid)
        if name=='get_inventory': result={'inventory':inventory(db,pid)}
        elif name=='get_product_details': result=serialize(record(db,Product,pid))
        elif name=='get_sales_history': result={'sales':[serialize(s) for s in db.scalars(select(Sale).where(Sale.product_id==pid).order_by(Sale.date)).all()]}
        elif name=='get_supplier_details' or name=='compare_suppliers': result={'suppliers':compare_suppliers(db,pid)}
        elif name=='get_supplier_performance': result={'suppliers':[supplier_performance(db,o['supplier_id']) for o in compare_suppliers(db,pid)]}
        elif name=='generate_demand_forecast': result=forecast(db,**args)
        elif name in ('calculate_reorder_point','calculate_safety_stock','calculate_order_quantity','optimize_replenishment'): result=replenishment(db,**args)
        elif name=='create_purchase_order_draft': result=draft_order(db,user,**args)
        elif name=='validate_purchase_order':
            po=record(db,PurchaseOrder,args['order_id'])
            result={'valid':po.quantity>0,'order':serialize(po),'approval_required':po.status=='draft'}
        elif name=='get_inventory_alerts': result={'alerts':alerts(db)}
        else: result={'inventory':inventory(db),'alerts':alerts(db)}
        if time.monotonic()-started>30:
            raise HTTPException(504,'Tool execution exceeded the 30-second deadline')
        # JSON serializability and finite numeric outputs are checked before return.
        import json
        json.dumps(result,allow_nan=False)
        status='completed'
        return result
    except Exception as exc:
        result={'error':exc.detail if isinstance(exc,HTTPException) else type(exc).__name__}
        raise
    finally:
        db.add(ToolCall(execution_id=execution_id,user_id=user.id,name=name,arguments=arguments,result=result,status=status))
        db.flush()
