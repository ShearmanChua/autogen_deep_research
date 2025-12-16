import os

from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.instrumentation._tracers import OITracer
from openinference.instrumentation.config import TraceConfig
from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from openinference.instrumentation import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from phoenix.otel import register
from utils.logger import get_logger

# from utils.tracer_fwd import ForwardingSpanProcessor
from utils.span_processor import AgentSpanProcessor

logger = get_logger()


def set_phoenix_tracer_provider(project_name: str, session_id: str):
    """
    Obtains the Phoenix tracer provider.

    Returns:
        The tracer provider instance registered by Phoenix.
    """
    os.environ["PROJECT_NAME"] = project_name
    otel_endpoint = os.environ.get("PHOENIX_ENDPOINT")
    msg_fwd = AgentSpanProcessor(
        OTLPSpanExporter(endpoint=otel_endpoint), session_id=session_id
    )
    trace_provider = register(project_name=project_name)
    trace_provider.add_span_processor(msg_fwd)
    OpenAIInstrumentor().instrument(tracer_provider=trace_provider)
    return trace_provider


def get_tracer():
    otel_endpoint = os.environ.get("PHOENIX_ENDPOINT")
    resource = Resource(
        attributes={
            ResourceAttributes.PROJECT_NAME: os.environ.get(
                "PROJECT_NAME", "PLACEHOLDER_project_name"
            )
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        AgentSpanProcessor(OTLPSpanExporter(otel_endpoint))
    )
    tracer = tracer_provider.get_tracer(__name__)
    return tracer
