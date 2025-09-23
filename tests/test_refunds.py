# tests/test_refunds.py
from uuid import UUID

def test_refund_is_idempotent(client):
    # create & pay
    body = {"user_id": "00000000-0000-0000-0000-000000000001", "amount_cents": 900, "currency": "USD"}
    order = client.post("/orders", json=body).json()
    order_id = order["id"]; UUID(order_id)

    pay = client.post(f"/orders/{order_id}/pay", headers={"Idempotency-Key": "pay1"})
    assert pay.status_code == 200 and pay.json()["status"] == "PAID"

    # refund
    r1 = client.post(f"/orders/{order_id}/refund", headers={"Idempotency-Key": "ref1"})
    assert r1.status_code == 200 and r1.json()["refunded"] is True

    # refund again with SAME key -> same JSON
    r2 = client.post(f"/orders/{order_id}/refund", headers={"Idempotency-Key": "ref1"})
    assert r2.status_code == 200 and r2.json() == r1.json()

    # ledger has 4 rows total (2 pay + 2 refund)
    rows = client.get(f"/orders/{order_id}/ledger").json()
    assert len(rows) == 4
    debits = sum(x["debit_cents"] for x in rows)
    credits = sum(x["credit_cents"] for x in rows)
    assert debits == credits == 900 * 2  # 900 DR/CR from pay + 900 DR/CR from refund
