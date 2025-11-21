"""
Observability Setup - Metrics and Tracing
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from prometheus_client import Counter, Histogram, Gauge

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
accounts_created_counter = Counter(
    'bank_accounts_created_total',
    'Total number of bank accounts created',
    ['status']
)

transfers_processed_counter = Counter(
    'bank_transfers_processed_total',
    'Total number of transfers processed',
    ['status', 'idempotency_hit']
)

transfer_duration = Histogram(
    'bank_transfer_duration_seconds',
    'Time spent processing transfers'
)

total_balance_gauge = Gauge(
    'bank_total_balance',
    'Total balance across all accounts'
)


def instrument_app(app):
    """Instrument FastAPI app with OpenTelemetry"""
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)

