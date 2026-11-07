from sqlalchemy import ForeignKey, String, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base, now

class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now, onupdate=now)

class User(Record, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(default='analyst')

class Warehouse(Record, Base):
    __tablename__ = 'warehouses'
    name: Mapped[str] = mapped_column(unique=True)
    location: Mapped[str]

class Product(Record, Base):
    __tablename__ = 'products'
    sku: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    category: Mapped[str]
    price: Mapped[float]
    holding_cost: Mapped[float] = mapped_column(default=4)
    ordering_cost: Mapped[float] = mapped_column(default=40)
    stockout_cost: Mapped[float] = mapped_column(default=15)
    capacity: Mapped[int] = mapped_column(default=2000)
    __table_args__ = (CheckConstraint('price > 0 AND capacity >= 0'),)

class Inventory(Record, Base):
    __tablename__ = 'inventory'
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'))
    quantity: Mapped[int]
    batch: Mapped[str] = mapped_column(default='')
    expiry: Mapped[str | None]
    __table_args__ = (UniqueConstraint('product_id', 'warehouse_id'), CheckConstraint('quantity >= 0'))

class Supplier(Record, Base):
    __tablename__ = 'suppliers'
    name: Mapped[str]
    email: Mapped[str]

class SupplierProduct(Record, Base):
    __tablename__ = 'supplier_products'
    supplier_id: Mapped[int] = mapped_column(ForeignKey('suppliers.id'), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    unit_price: Mapped[float]
    lead_days: Mapped[float]
    lead_std: Mapped[float] = mapped_column(default=1)
    moq: Mapped[int] = mapped_column(default=20)
    pack_size: Mapped[int] = mapped_column(default=10)
    available: Mapped[int] = mapped_column(default=2000)
    __table_args__ = (UniqueConstraint('supplier_id', 'product_id'), CheckConstraint('unit_price > 0 AND lead_days > 0 AND pack_size > 0 AND moq > 0'))

class Delivery(Record, Base):
    __tablename__ = 'deliveries'
    supplier_id: Mapped[int] = mapped_column(ForeignKey('suppliers.id'), index=True)
    promised_days: Mapped[float]
    actual_days: Mapped[float]

class Sale(Record, Base):
    __tablename__ = 'sales'
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    date: Mapped[str] = mapped_column(index=True)
    quantity: Mapped[int]
    __table_args__ = (UniqueConstraint('product_id', 'date'), CheckConstraint('quantity >= 0'))

class Movement(Record, Base):
    __tablename__ = 'stock_movements'
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'))
    quantity: Mapped[int]
    reason: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))

class PurchaseOrder(Record, Base):
    __tablename__ = 'purchase_orders'
    supplier_id: Mapped[int] = mapped_column(ForeignKey('suppliers.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'))
    quantity: Mapped[int]
    unit_price: Mapped[float]
    status: Mapped[str] = mapped_column(default='draft')
    requested_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    approved_at: Mapped[str | None]
    __table_args__ = (CheckConstraint('quantity > 0 AND unit_price > 0'),)

class StoredResult(Record, Base):
    __tablename__ = 'analysis_results'
    kind: Mapped[str] = mapped_column(index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey('products.id'))
    data: Mapped[dict] = mapped_column(JSON)

class Execution(Record, Base):
    __tablename__ = 'agent_executions'
    status: Mapped[str] = mapped_column(default='running')
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    data: Mapped[dict] = mapped_column(JSON, default=dict)

class ToolCall(Record, Base):
    __tablename__ = 'agent_tool_calls'
    execution_id: Mapped[int | None] = mapped_column(ForeignKey('agent_executions.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str]
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str]

class Audit(Record, Base):
    __tablename__ = 'audit_logs'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)

class ImportRecord(Record, Base):
    __tablename__ = 'imports'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str]
    rows: Mapped[int]
    filename: Mapped[str]
