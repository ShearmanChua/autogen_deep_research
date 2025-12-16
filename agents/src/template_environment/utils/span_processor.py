import json

from opentelemetry.sdk.trace import ReadableSpan, Span, SpanContext, _Span
from opentelemetry.context import Context
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from openinference.semconv.trace import SpanAttributes


class AgentSpanProcessor(SimpleSpanProcessor):
    def __init__(self, otel_span_exporter, session_id):
        super().__init__(otel_span_exporter)
        self.start_context = None
        self.start_trace_id = None
        self.start_span = None
        self.session_id = session_id

    def explode_dotted_dict(self, dotted_dict):
        result = {}
        for key, value in dotted_dict.items():
            keys = key.split(".")  # Split the key by dots
            d = result
            for part in keys[:-1]:  # Iterate through all parts except the last
                d = d.setdefault(part, {})  # Create a nested dictionary if missing
            d[keys[-1]] = value  # Set the final value
        return result

    def _classify_span(self, span: Span) -> Span:
        if self.start_context is None:
            self.start_context = span.context
            self.start_trace_id = span.context.trace_id
            self.start_span = span
        elif span._parent is None and span._context != self.start_context:
            span._parent = self.start_context
            span._context = SpanContext(
                trace_id=self.start_trace_id,
                span_id=span._context.span_id,
                trace_flags=span._context.trace_flags,
                is_remote=span._context.is_remote,
            )
        else:
            span._context = SpanContext(
                trace_id=self.start_trace_id,
                span_id=span._context.span_id,
                trace_flags=span._context.trace_flags,
                is_remote=span._context.is_remote,
            )
            current_parent_context = span._parent
            span._parent = SpanContext(
                trace_id=self.start_trace_id,
                span_id=current_parent_context.span_id,
                trace_flags=current_parent_context.trace_flags,
                is_remote=current_parent_context.is_remote,
            )

        span.set_attribute(SpanAttributes.SESSION_ID, self.session_id)
        attrib_dict = self.explode_dotted_dict(json.loads(span.to_json())["attributes"])
        if "recipient_agent_type" in attrib_dict:
            agent_message = json.loads(attrib_dict.get("message"))
            if "broadcast" in agent_message and agent_message["broadcast"]:
                return span
            span.set_attribute("openinference.span.kind", "AGENT")
            span._name = attrib_dict.get("recipient_agent_type")
            span.set_attribute("input.value", agent_message["context"][0]["content"])
        elif "tool_name" in attrib_dict:
            span.set_attribute("openinference.span.kind", "TOOL")

            span.set_attribute("input.value", attrib_dict.get("tool_args"))
            span.set_attribute("tool.name", attrib_dict.get("tool_name"))
            span.set_attribute("tool.description", attrib_dict.get("tool_description"))
        elif "gen_ai" in attrib_dict:
            span.set_attribute("openinference.span.kind", "TOOL")

            span.set_attribute("input.value", attrib_dict.get("input", {}).get("value"))
            span.set_attribute(
                "output.value", attrib_dict.get("output", {}).get("value")
            )
            span.set_attribute(
                "tool.name", attrib_dict.get("gen_ai", {}).get("tool", {}).get("name")
            )
            span.set_attribute(
                "tool.description",
                attrib_dict.get("gen_ai", {}).get("tool", {}).get("description"),
            )
        return span

    def on_start(self, span: Span, parent_context: Context) -> None:
        new_span = self._classify_span(span)
        super().on_start(new_span, parent_context)

    def on_end(self, span: ReadableSpan):
        """Called when a span ends. Creates a redacted copy and exports it."""
        super().on_end(span)
