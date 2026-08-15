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

# Gemini through its OpenAI-compatible endpoint. Point BASE_URL at
# http://localhost:11434/v1 to run the same code against a local Ollama model.
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Held fixed across both modes and written into every trace header.
MODEL = "gemini-3.1-flash-lite"
MAX_TOKENS = 4096
MAX_STEPS = 30
