# app/metrics.py
from prometheus_client import Counter, Histogram, make_asgi_app

# Counters
payments_total = Counter("payments_total", "Successful payment operations")
refunds_total = Counter("refunds_total", "Successful refund operations")

idempotency_hits = Counter(
    "idempotency_hits_total",
    "Idempotency cache hits (same key, same request)",
    ["endpoint"],
)
idempotency_conflicts = Counter(
    "idempotency_conflicts_total",
    "Key reused for different request (409)",
    ["endpoint"],
)
inflight_retries = Counter(
    "idempotency_inflight_total",
    "Requests returned 425 Too Early (key still in-flight)",
    ["endpoint"],
)

payment_errors = Counter("payment_errors_total", "Payment errors", ["type"])
refund_errors = Counter("refund_errors_total", "Refund errors", ["type"])

# Latency
payment_latency = Histogram("payment_latency_seconds", "Payment latency in seconds")
refund_latency = Histogram("refund_latency_seconds", "Refund latency in seconds")

# ASGI app for /metrics
metrics_asgi_app = make_asgi_app()
