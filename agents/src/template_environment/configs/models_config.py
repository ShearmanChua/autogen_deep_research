import os

MODEL_ENDPOINT = os.environ.get(
    "MODEL_ENDPOINT", "https://api.openai.com/v1/chat/completions"
)
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-2024-08-06")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "EMPTY")


model_cfg = {
    "base_url": MODEL_ENDPOINT,
    "model": MODEL_NAME,
    "temperature": 0,
    "api_key": MODEL_API_KEY,
    "model_capabilities": {
        "vision": False,
        "function_calling": True,
        "json_output": True,
    },
}
