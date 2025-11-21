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
totals_requests_total = Counter(
    'totals_requests_total',
    'Total number of totals requests',
    ['campaign_id', 'cache_hit']
)

cache_hit_ratio = Gauge(
    'cache_hit_ratio',
    'Cache hit ratio',
    ['cache_type']
)

totals_calculation_duration = Histogram(
    'totals_calculation_duration_seconds',
    'Time spent calculating totals',
    ['source']
)

materialized_view_age = Gauge(
    'materialized_view_age_seconds',
    'Age of materialized view data'
)


def instrument_app(app):
    """Instrument FastAPI app with OpenTelemetry"""
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)

