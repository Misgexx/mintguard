# app/models.py
from datetime import datetime, timezone
import enum
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer,
    String, CHAR, JSON, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"

def now_utc():
    return datetime.now(timezone.utc)

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(CHAR(3), nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="orders_amount_positive"),
    )

    ledger_entries = relationship("LedgerEntry", back_populates="order")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    account = Column(String, nullable=False)  # 'CASH' or 'REVENUE'
    debit_cents = Column(Integer, nullable=False, default=0)
    credit_cents = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    order = relationship("Order", back_populates="ledger_entries")

    __table_args__ = (
        CheckConstraint("debit_cents >= 0 AND credit_cents >= 0", name="ledger_nonneg"),
        CheckConstraint("(debit_cents = 0) <> (credit_cents = 0)", name="ledger_exactly_one_side"),
        CheckConstraint("account IN ('CASH','REVENUE')", name="ledger_account_valid"),
    )

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String, primary_key=True)
    request_fingerprint = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("key", name="idemp_key_unique"),
    )
