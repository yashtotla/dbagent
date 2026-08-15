"""Configuration for the project."""

from dotenv import load_dotenv

load_dotenv()

DSN = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "pw",
    "charset": "utf8mb4",
    "autocommit": True,
}

TASK_DB = "dbagent_task"

# OpenRouter's OpenAI-compatible endpoint. Point BASE_URL at
# http://localhost:11434/v1 to run the same code against a local Ollama model.
BASE_URL = "https://openrouter.ai/api/v1"
API_KEY_VAR = "OPEN_ROUTER_API_KEY"

# Held fixed across both modes and written into every trace header.
MODEL = "nvidia/nemotron-nano-9b-v2:free"
MAX_TOKENS = 4096
MAX_STEPS = 30
