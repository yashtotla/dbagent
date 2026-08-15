"""Configuration for the project."""

import os

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

# Per-process, because build_table starts with DROP DATABASE. A shared name lets
# two concurrent runs destroy each other's table mid-task
TASK_DB = f"dbagent_task_{os.getpid()}"

# Local Ollama, OpenAI-compatible. Point BASE_URL at a hosted provider's
# /v1 endpoint and change MODEL to run the same code against it.
BASE_URL = "http://localhost:11434/v1"
API_KEY_VAR = "OLLAMA_API_KEY"

# Held fixed across both modes and written into every trace header.
MODEL = "qwen2.5:7b"
MAX_TOKENS = 4096
MAX_STEPS = 30
