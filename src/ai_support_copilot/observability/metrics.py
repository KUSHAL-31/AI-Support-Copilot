from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "copilot_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "copilot_http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)
QUERY_LATENCY = Histogram("copilot_query_latency_ms", "End-to-end query latency in milliseconds")
INGESTION_COUNT = Counter("copilot_ingestions_total", "Ingestion jobs", ["status"])


def prometheus_payload() -> bytes:
    return generate_latest()
