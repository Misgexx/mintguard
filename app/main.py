from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from uuid import UUID, uuid4
from sqlalchemy import select, func  
from typing import List
from contextlib import asynccontextmanager
from app.db import engine, SessionLocal, ping_db
from app.models import Base, Order, OrderStatus, LedgerEntry
from app.schemas import OrderCreate, OrderOut, OrderDetail, LedgerEntryOut, LedgerSummaryOut
from app.services.payments import pay_order_idempotent  # <-- use the service
from app.services.refunds import refund_order_idempotent
from app.metrics import metrics_asgi_app 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs once at startup
    Base.metadata.create_all(bind=engine)
    yield
    # runs once at shutdown (nothing to clean up for now)

app = FastAPI(title="MintGuard Payments", lifespan=lifespan)


app.mount("/metrics", metrics_asgi_app)   


@app.get("/")
def root():
    return {"service": "mintguard", "docs": "/docs"}

@app.get("/healthz")
def healthz():
    try:
        ping_db()
        return {"ok": True, "db": "up"}
    except Exception:
        return {"ok": False, "db": "down"}

@app.post("/orders", response_model=OrderOut, tags=["orders"])
def create_order(payload: OrderCreate):
    currency = payload.currency.upper()
    with SessionLocal() as db:
        order = Order(
            id=uuid4(),
            user_id=payload.user_id,
            amount_cents=payload.amount_cents,
            currency=currency,
            status=OrderStatus.PENDING,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

@app.post("/orders/{order_id}/pay", tags=["orders"])
def pay_order(order_id: UUID, Idempotency_Key: str = Header(alias="Idempotency-Key")):
    if not Idempotency_Key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
    with SessionLocal() as db:
        status_code, body = pay_order_idempotent(db, order_id, Idempotency_Key)
        return JSONResponse(status_code=status_code, content=body)
@app.get("/orders/{order_id}", response_model=OrderDetail, tags=["orders"])
def get_order(order_id: UUID):
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order

@app.get("/orders/{order_id}/ledger", response_model=List[LedgerEntryOut], tags=["ledger"])
def get_order_ledger(order_id: UUID):
    with SessionLocal() as db:
        # 404 if order doesn't exist (nicer than returning empty)
        exists = db.get(Order, order_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Order not found")

        rows = db.execute(
            select(LedgerEntry).where(LedgerEntry.order_id == order_id)
        ).scalars().all()
        return rows
    
@app.get("/orders/{order_id}/ledger/summary", response_model=LedgerSummaryOut, tags=["ledger"])
def get_order_ledger_summary(order_id: UUID):
    with SessionLocal() as db:
        # ensure order exists
        exists = db.get(Order, order_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Order not found")

        totals = db.execute(
            select(
                func.coalesce(func.sum(LedgerEntry.debit_cents), 0).label("debits"),
                func.coalesce(func.sum(LedgerEntry.credit_cents), 0).label("credits"),
            ).where(LedgerEntry.order_id == order_id)
        ).one()

        return {
            "order_id": order_id,
            "total_debits": int(totals.debits or 0),
            "total_credits": int(totals.credits or 0),
        }
    
@app.post("/orders/{order_id}/refund", tags=["orders"])
def refund_order(order_id: UUID, Idempotency_Key: str = Header(alias="Idempotency-Key")):
    if not Idempotency_Key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
    with SessionLocal() as db:
        status_code, body = refund_order_idempotent(db, order_id, Idempotency_Key)
        return JSONResponse(status_code=status_code, content=body)    