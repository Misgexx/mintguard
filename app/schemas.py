from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"

class OrderCreate(BaseModel):
    user_id: UUID
    # Validate using Field constraints (keeps Pylance happy)
    amount_cents: int = Field(..., gt=0, description="Amount in cents, must be > 0")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 code like USD")

class OrderOut(BaseModel):
    id: UUID
    user_id: UUID
    amount_cents: int
    currency: str
    status: OrderStatus
class OrderDetail(OrderOut):
    created_at: datetime | None = None
    updated_at: datetime | None = None

class LedgerEntryOut(BaseModel):
    id: UUID
    order_id: UUID
    account: Literal["CASH", "REVENUE"]
    debit_cents: int
    credit_cents: int
    
class LedgerSummaryOut(BaseModel):
    order_id: UUID
    total_debits: int
    total_credits: int
