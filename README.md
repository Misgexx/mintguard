# 🍀 MintGuard

**Live API:** https://mintguard.onrender.com/docs  
**Repo:** https://github.com/Misgexx/mintguard

Stop accidental **double charges** with **idempotency keys** and keep books clean with a **double-entry ledger**.  
Includes **payments**, **refunds**, **metrics**, **Docker**, and **tests**.

---

## 🚦 What this is 

-What this is (plain English)

•	When people click “Pay” twice (bad Wi-Fi, refresh, impatient taps), most systems risk charging them twice.

•	MintGuard stops that: each payment attempt gets a unique Idempotency-Key. If the same request is retried, the system returns the same result instead of charging again.

•	Every transaction is written to a double-entry ledger (debit cash, credit revenue). Refunds write the exact reverse entries. That makes totals always balance and the history auditable


---

🛠 Tech Stack

FastAPI, Starlette

SQLAlchemy 2.x, psycopg

Pydantic / pydantic-settings

Prometheus client for metrics

Pytest (+ httpx) for tests

Docker / docker compose

Deployed on Render
---

## 🧪 One-minute demo (in the browser)

1. Open Swagger UI: **https://mintguard.onrender.com/docs**
2. `POST /orders` → create an order, copy the returned `id`.
3. `POST /orders/{order_id}/pay` with header **`Idempotency-Key: <any-uuid>`**.  
   Re-run with the **same key** → **same JSON**, no double charge.
4. `POST /orders/{order_id}/refund` with a **new** idempotency key → writes reversal entries.
5. `GET /orders/{order_id}/ledger` and `/ledger/summary` → see the DR/CR lines & totals.

_Heads-up: on free hosting, the first hit can be slow (cold start)._

---

## 🔌 Quick demo (PowerShell)

```powershell
# 1) Create order
$body = @{ user_id="00000000-0000-0000-0000-000000000001"; amount_cents=1200; currency="USD" } | ConvertTo-Json
$order = Invoke-RestMethod -Method Post -Uri "https://mintguard.onrender.com/orders" -ContentType "application/json" -Body $body
$order.id

# 2) Pay with idempotency key (safe to retry)
$key = [guid]::NewGuid().ToString()
Invoke-RestMethod -Method Post -Uri ("https://mintguard.onrender.com/orders/{0}/pay" -f $order.id) -Headers @{ "Idempotency-Key" = $key }

# 3) Retry same key → same JSON (no double charge)
Invoke-RestMethod -Method Post -Uri ("https://mintguard.onrender.com/orders/{0}/pay" -f $order.id) -Headers @{ "Idempotency-Key" = $key }

# 4) Refund (use a NEW key)
$rkey = [guid]::NewGuid().ToString()
Invoke-RestMethod -Method Post -Uri ("https://mintguard.onrender.com/orders/{0}/refund" -f $order.id) -Headers @{ "Idempotency-Key" = $rkey }

# 5) Inspect ledger
Invoke-RestMethod -Method Get -Uri ("https://mintguard.onrender.com/orders/{0}/ledger" -f $order.id) | ConvertTo-Json -Depth 5


📊 Metrics (Prometheus)

Request counters by route/status

Latency histograms

Payment/refund counters



✍️ Author

Made by Misgana Kebede.
Live API: https://mintguard.onrender.com/docs  
• Repo: https://github.com/Misgexx/mintguard