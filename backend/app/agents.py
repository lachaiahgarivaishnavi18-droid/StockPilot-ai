import json
import os
import logging
from fastapi import HTTPException
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from .models import Execution, StoredResult, Product
from .tools import execute, REGISTRY
from .services import replenishment, serialize
from .security import audit
from .security import require
from .services import record

AGENTS=['Inventory Monitoring','Demand Forecasting','Replenishment Planning','Supplier Analysis','Inventory Optimization','Purchase Order','Risk Detection','LLM Insight','Orchestrator']

class State(TypedDict, total=False):
    product_id:int
    create_draft:bool
    outputs:dict
    error:str
    awaiting_approval:bool

def run_workflow(db,user,product_id,create_draft=False):
    if create_draft:
        if user.role not in ('admin','approver','planner'):
            raise HTTPException(403,'Draft creation requires an administrator, approver, or planner. Analysts can use Run analysis.')
    record(db,Product,product_id)
    db.info['analysis_snapshot']=True
    execution=Execution(user_id=user.id,data={})
    db.add(execution)
    db.flush()
    def call(name,args):
        return execute(db,user,name,args,execution.id,allow_draft=create_draft)
    def node(label,fn):
        def wrapped(state):
            if state.get('error'): return {}
            try:
                output=fn(state)
                return {'outputs':{**state.get('outputs',{}),label:output}}
            except Exception as exc:
                return {'error':f'{label}: {getattr(exc,"detail",type(exc).__name__)}'}
        return wrapped
    graph=StateGraph(State)
    graph.add_node('monitor',node('inventory',lambda s:call('get_inventory',{'product_id':s['product_id']})))
    graph.add_node('forecast',node('forecast',lambda s:call('generate_demand_forecast',{'product_id':s['product_id'],'horizon':30})))
    graph.add_node('supplier',node('suppliers',lambda s:call('compare_suppliers',{'product_id':s['product_id']})))
    graph.add_node('plan',node('plan',lambda s:call('calculate_order_quantity',{'product_id':s['product_id']})))
    def optimize(s):
        # Registry call is retained as evidence; forecast-conditioned result is persisted separately.
        baseline=call('optimize_replenishment',{'product_id':s['product_id']})
        result=replenishment(db,s['product_id'],demand_forecast=s['outputs']['forecast'])
        db.add(StoredResult(kind='optimization',product_id=s['product_id'],data=result))
        return result
    graph.add_node('optimize',node('optimization',optimize))
    graph.add_node('risk',node('risks',lambda s:call('get_inventory_alerts',{})))
    def draft(s):
        sol=s['outputs']['optimization']['solution']
        return call('create_purchase_order_draft',{'product_id':s['product_id'],'supplier_id':sol['supplier_id'],'quantity':sol['quantity']})
    graph.add_node('draft',node('purchase_order',draft))
    def insights(s):
        r=s['outputs']['optimization']
        return {'mode':'deterministic demo','summary':f"{r['name']}: {r['available']} available, reorder point {r['reorder_point']}, recommended {r['quantity']} units. {r['reason']}.",'evidence':['inventory','forecast','suppliers','optimization'],'human_approval_required':bool(s['outputs'].get('purchase_order'))}
    graph.add_node('insight',node('insight',insights))
    graph.set_entry_point('monitor')
    for a,b in [('monitor','forecast'),('forecast','supplier'),('supplier','plan'),('plan','optimize'),('optimize','risk')]:
        graph.add_conditional_edges(a,lambda s, b=b: 'stop' if s.get('error') else b,{'stop':END,b:b})
    graph.add_conditional_edges('risk',lambda s:'stop' if s.get('error') else 'draft' if s.get('create_draft') and s['outputs']['optimization'].get('solution') else 'insight',{'stop':END,'draft':'draft','insight':'insight'})
    graph.add_edge('draft','insight')
    graph.add_edge('insight',END)
    app=graph.compile(checkpointer=MemorySaver())
    try:
        result=app.invoke({'product_id':product_id,'create_draft':create_draft,'outputs':{}}, {'configurable':{'thread_id':str(execution.id)}})
    except Exception as exc:
        logging.getLogger(__name__).exception('Agent workflow failed for execution %s',execution.id)
        result={'product_id':product_id,'create_draft':create_draft,'outputs':{},'error':f'Workflow execution failed ({type(exc).__name__}). Review execution logs.'}
    execution.status='failed' if result.get('error') else 'awaiting_approval' if result['outputs'].get('purchase_order') else 'completed'
    execution.data=result
    audit(db,user,'agents.run',{'execution_id':execution.id,'status':execution.status})
    db.commit()
    for key in ('analysis_snapshot','analysis_inventory','analysis_supplier_performance','analysis_offers','analysis_sales'):
        db.info.pop(key,None)
    return serialize(execution)

def assistant(db,user,question,product_id=None):
    provider=os.getenv('OPENAI_API_KEY')
    if provider:
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
            specs=[{'type':'function','function':{'name':n,'description':f'{kind} inventory tool','parameters':schema.model_json_schema()}} for n,(schema,kind) in REGISTRY.items() if kind!='draft']
            llm=ChatOpenAI(model=os.getenv('LLM_MODEL','gpt-4o-mini'),api_key=provider,base_url=os.getenv('OPENAI_BASE_URL') or None,timeout=30,max_retries=1).bind_tools(specs)
            messages=[SystemMessage(content='Answer inventory questions only using tool evidence. Never invent values. You cannot approve, draft or place orders. State if data is unavailable.'),HumanMessage(content=f'{question}\nSelected product_id={product_id}')]
            evidence=[]
            for _ in range(5):
                reply=llm.invoke(messages)
                messages.append(reply)
                if not reply.tool_calls:
                    if not evidence: raise ValueError('Provider did not retrieve evidence')
                    return {'mode':'LLM with application tools','answer':reply.content,'evidence':evidence}
                for tc in reply.tool_calls:
                    result=execute(db,user,tc['name'],tc['args'])
                    evidence.append({'tool':tc['name'],'result':result})
                    messages.append(ToolMessage(content=json.dumps(result),tool_call_id=tc['id']))
            raise ValueError('Tool turn limit reached')
        except Exception:
            provider_error='Configured provider unavailable; using deterministic evidence mode.'
    else: provider_error=None
    q=question.lower()
    if product_id is None:
        for product in db.scalars(select(Product)).all():
            if product.sku.lower() in q: product_id=product.id; break
    name='get_inventory_alerts'
    args={}
    if product_id:
        name='generate_demand_forecast' if any(w in q for w in ('forecast','predict','demand')) else 'compare_suppliers' if 'supplier' in q else 'calculate_order_quantity' if any(w in q for w in ('order','why','replenish','quantity')) else 'get_inventory'
        args={'product_id':product_id}
    result=execute(db,user,name,args)
    if name=='calculate_order_quantity': answer=f"{result['name']}: {result['available']} units available, reorder point {result['reorder_point']}, safety stock {result['safety_stock']}. Recommended quantity: {result['quantity']}. {result['reason']}."
    elif name=='generate_demand_forecast': answer=f"Forecast demand: {result['total_demand']} units over {result['horizon']} days, using {result['model']}. Held-out MAE: {result['test_metrics']['mae']:.2f}."
    elif name=='compare_suppliers': answer='Supplier ranking: '+', '.join(f"{r['supplier_name']} (score {r['score']}, ${r['unit_price']}, {r['lead_days']} days)" for r in result['suppliers'])
    elif name=='get_inventory': answer='; '.join(f"{r['name']}: {r['quantity']} units, status {r['status']}" for r in result['inventory'])
    else: answer=f"Found {len(result['alerts'])} inventory and supplier alerts. Select a product to ask for a forecast, supplier comparison or replenishment calculation."
    return {'mode':'Deterministic local demo — no LLM used','answer':answer,'notice':provider_error,'evidence':[{'tool':name,'result':result}]}
