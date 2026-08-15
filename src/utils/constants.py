"""Static registries for the project."""

# Alias -> the client settings needed to reach that model. Both are Qwen so the
# tool-call format is the same; only the endpoint differs.
MODEL_REGISTRY = {
    "qwen2.5-7b": {
        "model": "qwen2.5:7b",
        "base_url": "http://localhost:11434/v1",
        "api_key_var": "OLLAMA_API_KEY",
    },
    "qwen3.6-27b": {
        "model": "qwen/qwen3.6-27b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_var": "GROQ_API_KEY",
    },
}
