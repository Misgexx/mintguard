# tests/test_payments.py
from uuid import UUID

def test_pay_once_then_same_key_is_idempotent(client):
    # 1) create order
    body = {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "amount_cents": 1200,
        "currency": "USD",
    }
    r = client.post("/orders", json=body)
    assert r.status_code == 200
    order = r.json()
    order_id = order["id"]
    # sanity
    UUID(order_id)

    # 2) pay with key 'abc'
    r1 = client.post(f"/orders/{order_id}/pay", headers={"Idempotency-Key": "abc"})
    assert r1.status_code == 200
    assert r1.json()["status"] == "PAID"

    # 3) pay again with SAME key 'abc' -> identical outcome (no new ledger rows)
    r2 = client.post(f"/orders/{order_id}/pay", headers={"Idempotency-Key": "abc"})
    assert r2.status_code == 200
    assert r2.json() == r1.json()

    # 4) ledger has exactly two rows (DR CASH, CR REVENUE)
    r3 = client.get(f"/orders/{order_id}/ledger")
    assert r3.status_code == 200
    rows = r3.json()
    assert len(rows) == 2
    # quick sum check
    total_debits = sum(x["debit_cents"] for x in rows)
    total_credits = sum(x["credit_cents"] for x in rows)
    assert total_debits == 1200
    assert total_credits == 1200
