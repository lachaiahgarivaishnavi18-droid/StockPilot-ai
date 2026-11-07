import csv
import io
import json
from datetime import date
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from .models import Product, Sale, Inventory, Warehouse, ImportRecord
from .schemas import ProductInput
from .services import record
from .security import audit, require

class SaleRow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    product_id:int=Field(gt=0)
    date:date
    quantity:int=Field(ge=0,le=1000000)

class StockRow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    product_id:int=Field(gt=0)
    warehouse_id:int=Field(gt=0)
    quantity:int=Field(ge=0,le=1000000)

def parse(content,filename,kind,mapping):
    if len(content)>2*1024*1024: raise HTTPException(413,'Maximum upload size is 2 MB')
    try:
        decoded=content.decode('utf-8-sig')
        rows=json.loads(decoded) if filename.lower().endswith('.json') else list(csv.DictReader(io.StringIO(decoded))) if filename.lower().endswith('.csv') else None
        if not isinstance(rows,list) or not rows or len(rows)>5000: raise ValueError('Expected 1–5000 rows in CSV or JSON array')
        schema={'products':ProductInput,'sales':SaleRow,'inventory':StockRow}[kind]
        output=[]; errors=[]; seen=set()
        for i,row in enumerate(rows):
            try:
                if not isinstance(row,dict): raise ValueError('Row must be an object')
                mapped={mapping.get(k,k):v for k,v in row.items()}
                parsed=schema.model_validate(mapped).model_dump(mode='json')
                key=parsed.get('sku') or (parsed.get('product_id'),parsed.get('date',parsed.get('warehouse_id')))
                if key in seen: raise ValueError('Duplicate key in file')
                seen.add(key); output.append(parsed)
            except Exception as exc: errors.append({'row':i+1,'error':str(exc)[:400]})
        return {'rows':output,'errors':errors,'count':len(rows),'columns':list(rows[0]),'kind':kind}
    except HTTPException: raise
    except Exception as exc: raise HTTPException(422,f'Cannot parse upload: {str(exc)[:200]}')

def commit_import(db,user,parsed,filename,confirm):
    require(user,('admin','approver','planner'))
    if parsed['kind']=='inventory' and (not confirm or user.role not in ('admin','approver')):
        raise HTTPException(403,'Inventory replacement requires an approver and explicit confirmation')
    if parsed['errors']: raise HTTPException(422,parsed['errors'])
    try:
        for row in parsed['rows']:
            if parsed['kind']=='products':
                if db.scalar(select(Product).where(Product.sku==row['sku'])): raise ValueError(f"Duplicate SKU {row['sku']}")
                db.add(Product(**row))
            elif parsed['kind']=='sales':
                record(db,Product,row['product_id'])
                if db.scalar(select(Sale).where(Sale.product_id==row['product_id'],Sale.date==row['date'])): raise ValueError('Duplicate product/date in database')
                db.add(Sale(**row))
            else:
                p=record(db,Product,row['product_id']); record(db,Warehouse,row['warehouse_id'])
                if row['quantity']>p.capacity: raise ValueError('Quantity exceeds product capacity')
                existing=db.scalar(select(Inventory).where(Inventory.product_id==row['product_id'],Inventory.warehouse_id==row['warehouse_id']))
                if existing: existing.quantity=row['quantity']
                else: db.add(Inventory(**row))
        db.flush()
        db.add(ImportRecord(user_id=user.id,kind=parsed['kind'],rows=len(parsed['rows']),filename=filename[:200]))
        audit(db,user,'data.imported',{'kind':parsed['kind'],'rows':len(parsed['rows'])})
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc,HTTPException): raise
        raise HTTPException(422,str(exc)[:200])
    return {'imported':len(parsed['rows'])}
