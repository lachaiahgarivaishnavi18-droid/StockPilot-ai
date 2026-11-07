from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Credentials(Strict):
    email: str = Field(min_length=5, max_length=255, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default='Analyst', min_length=1, max_length=100)

class ProductInput(Strict):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    price: float = Field(gt=0, le=1e7)
    capacity: int = Field(default=2000, ge=0, le=10000000)
    holding_cost: float = Field(default=4, gt=0)
    ordering_cost: float = Field(default=40, gt=0)
    stockout_cost: float = Field(default=15, gt=0)

class BootstrapCredentials(Credentials):
    setup_token: str = Field(min_length=32, max_length=200)

class ProductArgs(Strict):
    product_id: int = Field(gt=0)

class ForecastArgs(ProductArgs):
    horizon: int = Field(default=30, ge=1, le=90)

class OptimizeArgs(ProductArgs):
    budget: float = Field(default=25000, ge=0, le=1e9)
    service_level: float = Field(default=.95, ge=.5, le=.999)

class DraftArgs(ProductArgs):
    supplier_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=10000000)

class OrderArgs(Strict):
    order_id: int = Field(gt=0)

class MovementArgs(ProductArgs):
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(ge=-1000000, le=1000000)
    reason: str = Field(min_length=4, max_length=300)
    confirm: Literal[True]

class SaleArgs(ProductArgs):
    date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    quantity: int = Field(ge=0, le=1000000)

class RunArgs(Strict):
    product_id: int = Field(gt=0)
    create_draft: bool = False

class QueryArgs(Strict):
    question: str = Field(min_length=3, max_length=2000)
    product_id: int | None = Field(default=None, gt=0)
