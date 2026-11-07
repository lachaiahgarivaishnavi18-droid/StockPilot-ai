import math
import random
from datetime import date, timedelta
from sqlalchemy import select
from .models import *
from .security import passwords

def seed(db):
    if db.scalar(select(Product.id).limit(1)):
        return {'loaded': False, 'message': 'Existing products preserved; sample loader is idempotent.'}
    rng = random.Random(42)
    warehouse = Warehouse(name='Central fulfillment', location='Bengaluru')
    db.add(warehouse)
    db.flush()
    suppliers = [Supplier(name=n, email=f'orders{i}@example.invalid') for i, n in enumerate(['Atlas Supply Co.', 'Northstar Trading', 'Meridian Wholesale'])]
    db.add_all(suppliers)
    db.flush()
    for s in suppliers:
        for _ in range(24):
            db.add(Delivery(supplier_id=s.id, promised_days=7, actual_days=rng.choice([5, 6, 7, 7, 8, 10])))
    names = [('Wireless Headphones', 'Electronics', 79), ('Organic Coffee Beans', 'Pantry', 18), ('Desk Lamp', 'Home', 35), ('Running Shoes', 'Lifestyle', 89), ('Steel Water Bottle', 'Lifestyle', 24), ('USB-C Hub', 'Electronics', 49), ('Cotton T-Shirt', 'Apparel', 22), ('Notebook Set', 'Office', 12), ('Yoga Mat', 'Lifestyle', 32), ('Green Tea', 'Pantry', 14), ('Monitor Stand', 'Office', 45), ('Canvas Backpack', 'Apparel', 59)]
    for i, (name, category, price) in enumerate(names):
        p = Product(sku=f'P{101+i}', name=name, category=category, price=price, capacity=3000, holding_cost=price*.2)
        db.add(p)
        db.flush()
        quantity = [28, 45, 0, 310, 95, 42, 1200, 220, 160, 2100, 320, 180][i]
        db.add(Inventory(product_id=p.id, warehouse_id=warehouse.id, quantity=quantity, batch=f'DEMO-{i+1}', expiry=(date.today()+timedelta(days=20 if i == 1 else 365)).isoformat()))
        for j, supplier in enumerate(suppliers):
            db.add(SupplierProduct(product_id=p.id, supplier_id=supplier.id, unit_price=round(price*(.48+j*.035), 2), lead_days=5+j*3, lead_std=1+j*.5, moq=20, pack_size=10, available=2500))
        for day in range(240):
            d = date.today()-timedelta(days=240-day)
            mean = 7+i*1.2
            qty = max(0, round(mean*(1+.25*math.sin(2*math.pi*d.weekday()/7)) + day*.008 + rng.gauss(0, 2)))
            db.add(Sale(product_id=p.id, date=d.isoformat(), quantity=qty))
    db.flush()
    return {'loaded': True, 'products': len(names), 'daily_sales': len(names)*240, 'synthetic': True}
