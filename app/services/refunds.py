# app/services/refunds.py
from datetime import datetime, timezone, timedelta
from time import perf_counter
from typing import Tuple, Dict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, LedgerEntry, IdempotencyKey
from app.metrics import (
    refunds_total, idempotency_hits, idempotency_conflicts,
    inflight_retries, refund_errors, refund_latency
)

LOCK_WINDOW_SECS = 15


def refund_order_idempotent(db: Session, order_id: UUID, idem_key: str) -> Tuple[int, Dict]:
    """
    Full refund flow (idempotent):
      - Bind Idempotency-Key to THIS request via fingerprint (method + path + order_id)
      - If cached response exists -> return it (with legacy binding check)
      - If in-flight -> 425 Too Early
      - Else do one atomic transaction:
          * lock order row, require PAID
          * write reversing entries: DR REVENUE, CR CASH
      - Cache response under the key
    Returns: (status_code, response_json)
    """
    start = perf_counter()
    now = datetime.now(timezone.utc)
    fingerprint = f"POST:/orders/{order_id}/refund"

    try:
        row = db.get(IdempotencyKey, idem_key)

        # Key used for a different request? -> 409
        if row and row.request_fingerprint and row.request_fingerprint != fingerprint:
            idempotency_conflicts.labels("refund").inc()
            raise HTTPException(status_code=409, detail="Idempotency-Key was used for a different request")

        # Completed response cached?
        if row and row.response_body is not None:
            if not row.request_fingerprint:
                cached_order = row.response_body.get("order_id")
                if cached_order and str(cached_order) != str(order_id):
                    idempotency_conflicts.labels("refund").inc()
                    raise HTTPException(status_code=409, detail="Idempotency-Key was used for a different request")
                row.request_fingerprint = fingerprint
                db.commit()
            idempotency_hits.labels("refund").inc()
            return (row.status_code or 200, row.response_body)

        # In-flight?
        if row and row.locked_until and row.locked_until > now:
            inflight_retries.labels("refund").inc()
            raise HTTPException(status_code=425, detail="Request in flight; retry shortly")

        # Set short in-flight lock + fingerprint
        lock_until = now + timedelta(seconds=LOCK_WINDOW_SECS)
        if not row:
            row = IdempotencyKey(key=idem_key, request_fingerprint=fingerprint, locked_until=lock_until)
            db.add(row)
        else:
            if not row.request_fingerprint:
                row.request_fingerprint = fingerprint
            row.locked_until = lock_until
        db.commit()

        # Do the refund atomically
        with db.begin():
            order = db.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()

            if not order:
                raise HTTPException(status_code=404, detail="Order not found")

            if order.status != OrderStatus.PAID:
                # MVP: only allow refund of PAID orders (we're not flipping status here)
                raise HTTPException(status_code=400, detail="Order not in PAID state")

            # Reverse original entries: DR REVENUE, CR CASH
            db.add(LedgerEntry(
                order_id=order.id, account="REVENUE",
                debit_cents=order.amount_cents, credit_cents=0
            ))
            db.add(LedgerEntry(
                order_id=order.id, account="CASH",
                debit_cents=0, credit_cents=order.amount_cents
            ))

            resp = {"order_id": str(order.id), "refunded": True}

        # Cache response and clear lock
        row.status_code = 200
        row.response_body = resp
        row.locked_until = None
        db.commit()

        refunds_total.inc()
        return (200, resp)

    except HTTPException as e:
        kind = "409_conflict" if e.status_code == 409 else (
               "425_inflight" if e.status_code == 425 else
               f"{e.status_code}")
        refund_errors.labels(kind).inc()
        raise
    finally:
        refund_latency.observe(perf_counter() - start)
