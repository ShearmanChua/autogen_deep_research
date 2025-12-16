import os

# TODO: Replace all PLACEHOLDER with concrete names

delegate_cfg = {
    "description": (
        "Call this tool to delegate your task to other agents if there "
        "are any tasks outside of your expertise. "
        "Only delegate to these agents:\n\n{agents}\n\n"
        "Each DelegationTask data model should contain the fields "
        "'task', 'agent' and 'name'."
    )
}

PLACEHOLDER_tool_cfg = {"description": ""}

# default tools
rag_cfg = {
    "description": (
        "Given the task, break it down into smaller tasks "
        "that would retrive relevant information. "
        "Call this tool to find the domain knowledge required "
        "from the agent to complete the task. "
        "Provide your name and a unique query specific to the "
        "agent role. Remember to provide your name as a parameter "
        "for this tool."
    ),
    "weaviate_client_configs": {
        "http_host": os.environ.get("WEAVIATE_HOST", "weaviate"),
        "http_port": os.environ.get("WEAVIATE_PORT", 8081),
        "http_secure": False,
        "grpc_host": os.environ.get("WEAVIATE_HOST", "weaviate"),
        "grpc_port": os.environ.get("WEAVIATE_GRPC_PORT", 50051),
        "grpc_secure": False,
    },
    "weaviate_collection": "documents",
    "weaviate_query_kwargs": {
        "query_properties": ["content^2", "extended_content"],
        "alpha": 0.8,
        "limit": 10,
    },
    "weaviate_content_field": "content",
    "embedding_api_endpoint": "http://localhost:8000/embeddings",
    "embedding_model": "bge-m3",
}
