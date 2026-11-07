import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['JWT_SECRET']='test-only-signing-key-with-at-least-32-characters'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base,get_db
from app.main import app,requests
from app.models import User,Product,Sale,ToolCall,PurchaseOrder
from app.security import passwords
from app.seed import seed
from app.services import replenishment
from app.services import inventory,alerts
from app.tools import execute

@pytest.fixture()
def context():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as db:
        user=User(email='admin@test.local',name='Admin',password_hash=passwords.hash('Test-password-2026!'),role='admin')
        db.add(user);seed(db);db.commit()
    def dependency():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=dependency
    requests.clear()
    with TestClient(app) as client:
        result=client.post('/api/auth/login',json={'email':'admin@test.local','password':'Test-password-2026!'})
        assert result.status_code==200,result.text
        client.headers['Authorization']='Bearer '+result.json()['access_token']
        yield client,factory
    app.dependency_overrides.clear()

def test_auth_permissions(context):
    c,_=context
    assert c.get('/api/auth/me').json()['role']=='admin'
    r=c.post('/api/auth/register',json={'email':'reader@test.local','password':'Reader-password-2026!'})
    assert r.status_code==201
    assert r.json()['user']['role']=='analyst'
    c.headers['Authorization']='Bearer '+r.json()['access_token']
    assert c.post('/api/demo/load',json={}).status_code==403
    assert c.get('/api/audit').status_code==403
    c.headers.clear()
    assert c.get('/api/inventory').status_code in (401,403)

def test_cloud_administrator_setup_is_single_use(context,monkeypatch):
    c,factory=context
    secret='test-bootstrap-token-with-at-least-32-characters'
    monkeypatch.setenv('BOOTSTRAP_TOKEN',secret)
    body={'email':'owner@test.local','password':'Owner-password-2026!','name':'Owner','setup_token':'wrong-token-with-at-least-32-characters'}
    assert c.post('/api/auth/bootstrap',json=body).status_code==403
    with factory() as db:
        db.scalar(select(User)).role='analyst';db.commit()
    body['setup_token']=secret
    r=c.post('/api/auth/bootstrap',json=body)
    assert r.status_code==201,r.text
    assert r.json()['user']['role']=='admin'
    assert c.post('/api/auth/bootstrap',json=body).status_code==409

def test_product_inventory_and_reports(context):
    c,_=context
    r=c.post('/api/products',json={'sku':'T1','name':'Test','category':'Office','price':20})
    assert r.status_code==201
    assert c.get('/api/products?search=Test').json()['total']==1
    r=c.post('/api/inventory/movements',json={'product_id':1,'warehouse_id':1,'quantity':10,'reason':'Cycle count','confirm':True})
    assert r.status_code==200,r.text
    assert r.json()['quantity']==38
    assert c.post('/api/inventory/movements',json={'product_id':1,'warehouse_id':1,'quantity':-1000,'reason':'bad adjustment','confirm':True}).status_code==422
    assert c.get('/api/reports').json()['summary']['total_products']==13

def test_forecasting_and_evaluation(context):
    c,_=context
    r=c.post('/api/forecast/generate',json={'product_id':1,'horizon':14})
    assert r.status_code==200,r.text
    f=r.json()
    assert len(f['forecast'])==14
    assert sum(f['split'].values())==240
    assert len(f['validation'])>=3
    assert f['test_metrics']['mae']>=0
    assert all(p['lower']<=p['predicted']<=p['upper'] for p in f['forecast'])
    assert c.get('/api/forecast/1').json()['model']==f['model']

def test_replenishment_constraints(context):
    c,factory=context
    with factory() as db:
        r=replenishment(db,1)
        assert r['safety_stock']>=0
        assert r['reorder_point']==pytest.approx(r['daily_demand']*r['lead_days']+r['safety_stock'],abs=.1)
        assert r['quantity']%10==0
        assert r['solution']['purchase_cost']<=25000
        assert r['quantity']+r['available']<=3000
        zero=replenishment(db,1,budget=0)
        assert zero['quantity']==0 and not zero['feasible']
    summary=c.get('/api/analytics/summary')
    assert summary.status_code==200,summary.text
    assert summary.json()['replenishment_recommendations']>0

def test_supplier_and_human_approval(context):
    c,_=context
    assert len(c.get('/api/suppliers/compare?product_id=1').json())==3
    r=c.post('/api/purchase-orders/draft',json={'product_id':1,'supplier_id':1,'quantity':100})
    assert r.status_code==201,r.text
    ident=r.json()['id']
    r=c.post(f'/api/purchase-orders/{ident}/approve')
    assert r.status_code==200,r.text
    assert r.json()['approved_by'] and r.json()['approved_at']
    assert c.post(f'/api/purchase-orders/{ident}/approve').status_code==409
    assert any(a['action']=='purchase_order.approved' for a in c.get('/api/audit').json())

def test_import_preview_and_transaction(context):
    c,factory=context
    content='SKU,Title,category,price\nIMPORT1,Imported,Office,30\n'
    data={'kind':'products','mapping':'{"SKU":"sku","Title":"name"}','preview':'true'}
    r=c.post('/api/import',data=data,files={'file':('products.csv',content,'text/csv')})
    assert r.status_code==200,r.text
    assert r.json()['rows'][0]['sku']=='IMPORT1'
    data['preview']='false'
    assert c.post('/api/import',data=data,files={'file':('products.csv',content,'text/csv')}).json()['imported']==1
    content='sku,name,category,price\nROLLBACK,First,Office,5\nIMPORT1,Duplicate,Office,5\n'
    data['mapping']='{}'
    assert c.post('/api/import',data=data,files={'file':('p.csv',content)}).status_code==422
    assert c.get('/api/products?search=ROLLBACK').json()['total']==0
    invalid='product_id,date,quantity\n1,not-a-date,-2\n'
    r=c.post('/api/import',data={'kind':'sales','preview':'true'},files={'file':('s.csv',invalid)})
    assert r.status_code==200 and r.json()['errors']

def test_real_agent_tools_and_fallback(context):
    c,factory=context
    r=c.post('/api/agents/run',json={'product_id':1,'create_draft':True})
    assert r.status_code==200,r.text
    run=r.json()
    assert run['status']=='awaiting_approval',run
    detail=c.get('/api/agents/executions/'+str(run['id'])).json()
    assert len(detail['calls'])>=7
    assert all(t['status']=='completed' for t in detail['calls'])
    assert run['data']['outputs']['purchase_order']['status']=='draft'
    answer=c.post('/api/assistant/query',json={'question':'Why should I order?','product_id':1})
    assert answer.status_code==200,answer.text
    assert answer.json()['evidence'][0]['tool']=='calculate_order_quantity'
    with factory() as db:
        user=db.scalar(select(User))
        with pytest.raises(Exception):execute(db,user,'create_purchase_order_draft',{'product_id':1,'supplier_id':1,'quantity':100})
        assert db.scalars(select(ToolCall).where(ToolCall.status=='failed')).first()

def test_agent_snapshot_bounds_queries_and_preserves_results(context):
    from sqlalchemy import event
    c,factory=context
    with factory() as db:
        expected=inventory(db)
        calls=[]
        def track(*args): calls.append(args[2])
        event.listen(db.bind,'before_cursor_execute',track)
        try:
            db.info['analysis_snapshot']=True
            assert inventory(db)==expected
            assert len(calls)<=8
            calls.clear()
            assert inventory(db,1)[0]==expected[0]
            alerts(db)
            assert len(calls)<=1
        finally:
            event.remove(db.bind,'before_cursor_execute',track)

def test_analyst_draft_denied_before_workflow(context):
    from app.models import Execution
    c,factory=context
    response=c.post('/api/auth/register',json={'email':'analyst@test.local','password':'Analyst-password-2026!'})
    c.headers['Authorization']='Bearer '+response.json()['access_token']
    response=c.post('/api/agents/run',json={'product_id':1,'create_draft':True})
    assert response.status_code==403,response.text
    assert 'Run analysis' in response.json()['detail']
    with factory() as db:
        assert db.scalar(select(Execution.id)) is None
    response=c.post('/api/agents/run',json={'product_id':1,'create_draft':False})
    assert response.status_code==200,response.text
    assert response.json()['status']=='completed',response.json()
