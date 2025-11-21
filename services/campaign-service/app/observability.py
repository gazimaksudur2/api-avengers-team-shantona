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
campaigns_created_counter = Counter(
    'campaigns_created_total',
    'Total number of campaigns created',
    ['category', 'status']
)

campaign_operations_duration = Histogram(
    'campaign_operations_duration_seconds',
    'Time spent on campaign operations',
    ['operation']
)


def instrument_app(app):
    """Instrument FastAPI app with OpenTelemetry"""
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)

