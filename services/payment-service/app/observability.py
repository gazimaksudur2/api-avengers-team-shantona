"""
Observability Setup - Metrics and Tracing
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from prometheus_client import Counter, Histogram

from app.config import settings
from app.database import engine

# ==================
# OpenTelemetry Setup
# ==================
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

# ==================
# Prometheus Metrics
# ==================
payment_processed_counter = Counter(
    'payment_processed_total',
    'Total number of payments processed',
    ['status', 'gateway']
)

webhook_processed_counter = Counter(
    'webhook_processed_total',
    'Total number of webhooks processed',
    ['status', 'idempotency_hit']
)

payment_duration = Histogram(
    'payment_processing_duration_seconds',
    'Time spent processing payments'
)

idempotency_cache_hits = Counter(
    'idempotency_cache_hits_total',
    'Number of idempotency cache hits',
    ['cache_type']
)


def instrument_app(app):
    """Instrument FastAPI app with OpenTelemetry"""
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)


