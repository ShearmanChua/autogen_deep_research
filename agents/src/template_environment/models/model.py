from autogen_ext.models.openai import OpenAIChatCompletionClient
from configs.models_config import model_cfg

model = OpenAIChatCompletionClient(
    base_url=model_cfg["base_url"],
    model=model_cfg["model"],
    temperature=model_cfg["temperature"],
    api_key=model_cfg["api_key"],
    model_capabilities=model_cfg["model_capabilities"],
)
