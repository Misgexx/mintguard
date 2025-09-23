# tests/test_idempotency_conflict.py
def test_reusing_key_on_different_order_returns_409_for_pay(client):
    body = {"user_id": "00000000-0000-0000-0000-000000000001", "amount_cents": 500, "currency": "USD"}

    a = client.post("/orders", json=body).json()
    b = client.post("/orders", json=body).json()

    # use key 'abc' on order A
    r1 = client.post(f"/orders/{a['id']}/pay", headers={"Idempotency-Key": "abc"})
    assert r1.status_code == 200

    # reuse key 'abc' on a different order B -> 409
    r2 = client.post(f"/orders/{b['id']}/pay", headers={"Idempotency-Key": "abc"})
    assert r2.status_code == 409
    assert "different request" in r2.json()["detail"]
