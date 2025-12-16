import json
import wrapt
import functools
from opentelemetry.trace import get_current_span, Status, StatusCode
from inspect import signature
from utils.logger import get_logger

logger = get_logger()

def trace_span_info(func):

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        current_span = get_current_span()

        # Log signature
        try:
            sig = str(signature(func))
            current_span.set_attribute("tool.parameters", sig)
        except Exception:
            current_span.set_attribute("tool.parameters", "Signature unavailable")

        # Log parameters
        try:
            bound = signature(func).bind(*args, **kwargs)
            args_dict = bound.arguments

            # Remove "self" if present
            if "self" in args_dict:
                args_without_self = {k: v for k, v in args_dict.items() if k != "self"}
            else:
                args_without_self = dict(args_dict)
            param_values = dict(args_without_self)
            current_span.set_attribute("input.value", json.dumps(param_values, indent=4))
        except Exception as e:
            current_span.set_attribute("input.value", f"Parameter logging failed: {e}")

        try:
            result = await func(*args, **kwargs)
            current_span.set_attribute("status", "OK")
        except Exception as e:
            current_span.set_attribute("output.value", f"Exception: {e}")
            current_span.set_attribute("status", "ERROR")
            raise

        current_span.set_attribute("output.value", str(result))
        return result

    # --- THE IMPORTANT FIX ---
    def __get__(instance, owner):
        # Bind self correctly
        return functools.partial(wrapper, instance)

    wrapper.__get__ = __get__  # inject descriptor

    return wrapper
