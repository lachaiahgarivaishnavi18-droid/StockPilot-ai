"""Reproduce the graph against PostgreSQL inside a rolled-back transaction."""
import json
import os
import sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
for line in (root/'.deployment/.env.local').read_text().splitlines():
    if line.startswith('DATABASE_URL='):
        raw=line.split('=',1)[1]
        os.environ['DATABASE_URL']=json.loads(raw) if raw.startswith('"') else raw
sys.path.insert(0,str(root/'backend'))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User,Product
from app.agents import run_workflow
with SessionLocal() as db:
    user=db.scalar(select(User).where(User.role=='admin'))
    product=db.scalar(select(Product).where(Product.sku=='P102'))
    if user is None or product is None:
        raise RuntimeError('Cloud reproduction requires the existing administrator and sample product')
    db.commit=db.flush
    try:
        import time
        started=time.monotonic()
        result=run_workflow(db,user,product.id,True)
        print(json.dumps({'status':result['status'],'error':result['data'].get('error'),'elapsed_seconds':round(time.monotonic()-started,2),'draft_created':bool(result['data'].get('outputs',{}).get('purchase_order'))}))
    finally:
        db.rollback()
