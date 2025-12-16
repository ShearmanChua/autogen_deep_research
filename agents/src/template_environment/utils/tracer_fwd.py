import json
from typing import Any, Dict, Optional

import requests
from autogen_core.models import UserMessage
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.trace import Span


class ForwardingSpanProcessor(SpanProcessor):
    def __init__(self, exporter: SpanExporter, forward_endpoint: str = None):
        """
        Initialize the PII redacting processor with an exporter and optional patterns.

        Args:
            exporter: The span exporter to use after PII redaction
            pii_patterns: Dictionary of pattern names and their regex patterns
        """
        self.forward_endpoint = forward_endpoint
        self._exporter = exporter

    def explode_dotted_dict(self, dotted_dict):
        result = {}
        for key, value in dotted_dict.items():
            keys = key.split(".")  # Split the key by dots
            d = result
            for part in keys[:-1]:  # Iterate through all parts except the last
                d = d.setdefault(part, {})  # Create a nested dictionary if missing
            d[keys[-1]] = value  # Set the final value
        return result

    def _redact_string(self, value: str) -> str:
        """Redact PII from any string value."""
        redacted = value
        for pattern_name, pattern in self._compiled_patterns.items():
            redacted = pattern.sub(f"[REDACTED_{pattern_name.upper()}]", redacted)
        return redacted

    def _redact_value(self, value: Any) -> Any:
        """
        Redact PII from any value type.
        Handles strings, numbers, booleans, lists, and dictionaries.
        """
        if isinstance(value, str):
            try:
                # Try to parse as JSON first
                json_obj = json.loads(value)
                return json.dumps(self._redact_value(json_obj))
            except json.JSONDecodeError:
                # If not valid JSON, treat as regular string
                return self._redact_string(value)
        elif isinstance(value, dict):
            return {k: self._redact_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._redact_value(item) for item in value]
        elif isinstance(value, (int, float, bool, type(None))):
            return value
        else:
            # Convert any other types to string and redact
            return self._redact_string(str(value))

    def _redact_span_attributes(self, span: ReadableSpan) -> Dict[str, Any]:
        """
        Create a new dictionary of redacted span attributes.
        """
        redacted_attributes = {}

        for key, value in span.attributes.items():
            # Skip certain metadata attributes that shouldn't contain PII
            if key in {"service.name", "telemetry.sdk.name", "telemetry.sdk.version"}:
                redacted_attributes[key] = value
                continue

            try:
                redacted_value = self._redact_value(value)
                redacted_attributes[key] = redacted_value
            except Exception as e:
                redacted_attributes[key] = "[REDACTION_ERROR]"
                print(f"Error redacting attribute {key}: {str(e)}")

        return redacted_attributes

    def _forward_span(self, span: ReadableSpan) -> ReadableSpan:
        """
        Create a new span with redacted attributes instead of modifying the original.
        """
        # Create redacted attributes

        # Create a new span with redacted name and attributes

        # Handle events
        # redacted_events = []
        # print("Span Details", span.name, span.get_span_context(), span.parent,
        # span.resource, span.links, span.kind, span.status)
        # for event in span.events:
        #     redacted_event_attrs = {
        #         k: self._redact_value(v) for k, v in event.attributes.items()
        #     }
        #     # Create new event with redacted attributes
        #     from opentelemetry.sdk.trace import Event
        #     redacted_event = Event(
        #         name=event.name,
        #         attributes=redacted_event_attrs,
        #         timestamp=event.timestamp
        #     )
        #     redacted_events.append(redacted_event)

        # Create new span with redacted data

        if span.name == "ChatCompletion":
            package_msg = """"""
            attrib_dict = self.explode_dotted_dict(
                json.loads(span.to_json())["attributes"]
            )
            input_msgs = attrib_dict["llm"]["input_messages"]
            output_msg = attrib_dict["llm"]["output_messages"]["0"]
            messages_list = [input_msgs[i] for i in input_msgs]
            participants = []

            for part in messages_list:
                package_msg += f"""{part["message"]["role"]} """
                if "name" in part["message"]:
                    package_msg += f""" (@{part["message"]["name"]}) """
                    participants.append(part["message"]["name"])
                else:
                    participants.append("")
                if "content" in part["message"]:
                    if "AssistantMessage(content=" in part["message"]["content"]:
                        part_msgs = eval(part["message"]["content"])
                        for subpart in part_msgs:
                            if isinstance(subpart[-1][-1], UserMessage):
                                package_msg += f"""\n{subpart[-1][-1].content}\n\n "
                                    "----------------------- \n\n"""
                            else:
                                package_msg += f"""\n{subpart[-1][-1][-1].content}\n\n "
                                    "----------------------- \n\n"""
                    else:
                        package_msg += (
                            f"""\n{part["message"]["content"]}\n\n """
                            """----------------------- \n\n"""
                        )
                else:
                    package_msg += """\n\n ----------------------- \n\n"""

            if "tool_calls" in output_msg["message"]:
                tool_used = output_msg["message"]["tool_calls"]["0"]["tool_call"][
                    "function"
                ]
                if tool_used["name"] == "delegate_tasks":
                    tool_args = eval(tool_used["arguments"])["delegation_tasks"]
                    if isinstance(tool_args, str):  # is a str
                        tool_args = json.loads(tool_args)
                    conversation_header = (
                        f"{participants[-1]} delegating to "
                        f"{', '.join(target['agent'] for target in tool_args)}"
                    )
                else:
                    conversation_header = (
                        f"{participants[-1]} used tool: {tool_used['name']}"
                    )
            else:
                participants = list(filter(None, participants))
                conversation_header = f"Conversation between {', '.join(participants)}"
            _ = requests.post(
                "http://frontend:3001/trace",
                json={"text": conversation_header + "\n" + package_msg},
            )
        _ = ReadableSpan(
            name=span.name,
            context=span.get_span_context(),
            parent=span.parent,
            resource=span.resource,
            events=span.events,
            links=span.links,
            kind=span.kind,
            status=span.status,
            start_time=span.start_time,
            end_time=span.end_time,
            instrumentation_info=span.instrumentation_info,
        )
        return span

    def on_start(self, span: Span, parent_context: Optional[Any] = None):
        """Called when a span starts."""
        pass

    def on_end(self, span: ReadableSpan):
        """Called when a span ends. Creates a redacted copy and exports it."""
        redacted_span = self._forward_span(span)
        self._exporter.export([redacted_span])

    def shutdown(self):
        """Shuts down the processor and exporter."""
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000):
        """Forces flush of pending spans."""
        self._exporter.force_flush(timeout_millis)
