from autogen_core.tools import FunctionTool
from opentelemetry import trace
from configs.tools_config import PLACEHOLDER_tool_cfg
from tools.tool_tracing_utils import trace_span_info

# TODO: Replace all PLACEHOLDER with concrete names


@trace_span_info
async def PLACEHOLDER_tool() -> str:
    """
    Extracts the lab order information from a document based on an admission ID.

    Returns:
        str: A string containing the lab order information if found, or "NIL" if the
        "LABS" section is not found.
    """
    current_span = trace.get_current_span()
    current_span.set_attribute("tool.parameters", str(placeholder_tool._signature))

    current_span.set_attribute("output.value", "OUTPUT_AS_STRING")
    # DO SOMETHING
    return ""


placeholder_tool = FunctionTool(
    PLACEHOLDER_tool_cfg, description=PLACEHOLDER_tool_cfg["description"]
)
