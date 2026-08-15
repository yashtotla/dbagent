"""Configuration for the project."""

import os

from dotenv import load_dotenv

from src.utils.constants import MODEL_REGISTRY

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
# two concurrent runs destroy each other's table mid-task.
TASK_DB = f"dbagent_task_{os.getpid()}"

# Held fixed across both modes and written into every trace header.
MAX_TOKENS = 4096
MAX_STEPS = 30


def resolve_model(alias: str) -> dict:
    """Return a model's client settings with its API key read from the environment."""
    entry = MODEL_REGISTRY[alias]
    return {**entry, "api_key": os.environ[entry["api_key_var"]]}
