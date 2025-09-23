# app/services/payments.py
from datetime import datetime, timezone, timedelta
from time import perf_counter
from typing import Tuple, Dict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, LedgerEntry, IdempotencyKey
from app.metrics import (
    payments_total, idempotency_hits, idempotency_conflicts,
    inflight_retries, payment_errors, payment_latency
)

# How long a request with a given idempotency key is considered "in flight"
LOCK_WINDOW_SECS = 15


def pay_order_idempotent(db: Session, order_id: UUID, idem_key: str) -> Tuple[int, Dict]:
    """
    Idempotent payment flow:
      - Bind Idempotency-Key to THIS request via a fingerprint (method + path + order_id)
      - If a response for this key is cached -> return it (no duplicate side effects)
        * Hardened: legacy rows without a fingerprint are validated against cached order_id
      - If request with this key is currently in-flight -> 425 Too Early
      - Else do one atomic transaction:
          * lock order row
          * if PENDING: write DR CASH / CR REVENUE and mark PAID
          * if already PAID: no-op
      - Cache exact response under the key
    Returns: (status_code, response_json)
    """
    start = perf_counter()
    now = datetime.now(timezone.utc)
    fingerprint = f"POST:/orders/{order_id}/pay"

    try:
        row = db.get(IdempotencyKey, idem_key)

        # Same key but for a different request? -> 409
        if row and row.request_fingerprint and row.request_fingerprint != fingerprint:
            idempotency_conflicts.labels("pay").inc()
            raise HTTPException(status_code=409, detail="Idempotency-Key was used for a different request")

        # Completed response cached?
        if row and row.response_body is not None:
            # Legacy hardening: if fingerprint missing, bind only if same order
            if not row.request_fingerprint:
                cached_order = row.response_body.get("order_id")
                if cached_order and str(cached_order) != str(order_id):
                    idempotency_conflicts.labels("pay").inc()
                    raise HTTPException(status_code=409, detail="Idempotency-Key was used for a different request")
                row.request_fingerprint = fingerprint
                db.commit()
            idempotency_hits.labels("pay").inc()
            return (row.status_code or 200, row.response_body)

        # In-flight lock active?
        if row and row.locked_until and row.locked_until > now:
            inflight_retries.labels("pay").inc()
            raise HTTPException(status_code=425, detail="Request in flight; retry shortly")

        # Set / refresh in-flight lock and persist fingerprint
        lock_until = now + timedelta(seconds=LOCK_WINDOW_SECS)
        if not row:
            row = IdempotencyKey(key=idem_key, request_fingerprint=fingerprint, locked_until=lock_until)
            db.add(row)
        else:
            if not row.request_fingerprint:
                row.request_fingerprint = fingerprint
            row.locked_until = lock_until
        db.commit()

        # Do the payment atomically with the order row locked
        with db.begin():
            order = db.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()

            if not order:
                raise HTTPException(status_code=404, detail="Order not found")

            if order.status == OrderStatus.PAID:
                resp = {"order_id": str(order.id), "status": "PAID"}
            else:
                # Double-entry: DR CASH, CR REVENUE
                db.add(LedgerEntry(
                    order_id=order.id, account="CASH",
                    debit_cents=order.amount_cents, credit_cents=0
                ))
                db.add(LedgerEntry(
                    order_id=order.id, account="REVENUE",
                    debit_cents=0, credit_cents=order.amount_cents
                ))
                order.status = OrderStatus.PAID
                resp = {"order_id": str(order.id), "status": "PAID"}

        # Cache the response and clear the lock
        row.status_code = 200
        row.response_body = resp
        row.locked_until = None
        db.commit()

        payments_total.inc()
        return (200, resp)

    except HTTPException as e:
        kind = "409_conflict" if e.status_code == 409 else (
               "425_inflight" if e.status_code == 425 else
               f"{e.status_code}")
        payment_errors.labels(kind).inc()
        raise
    finally:
        payment_latency.observe(perf_counter() - start)
