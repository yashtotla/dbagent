"""Static registries for the project."""

# Alias -> the client settings needed to reach that model. The provider is part of
# the alias because it changes behaviour: the same qwen3.6-27b emitted XML instead
# of JSON tool calls on 12 Groq calls and on none of the Alibaba ones.
MODEL_REGISTRY = {
    "qwen2.5-7b": {
        "model": "qwen2.5:7b",
        "base_url": "http://localhost:11434/v1",
        "api_key_var": "OLLAMA_API_KEY",
    },
    "qwen3.6-27b-groq": {
        "model": "qwen/qwen3.6-27b",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_var": "GROQ_API_KEY",
    },
    "qwen3.6-27b-ali": {
        "model": "qwen3.6-27b",
        "base_url": "https://ws-1orklmqwxft5uvut.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        "api_key_var": "ALIBABA_API_KEY",
    },
}
