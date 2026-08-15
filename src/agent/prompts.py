"""System prompts and tool schemas, held fixed across both modes."""

SYSTEM = """You are completing one task against a single MySQL table.

The task gives you the table name and its column names. Identifiers may contain
spaces and punctuation, so wrap every one of them in backticks.

Call execute_sql to run one statement. SELECT, INSERT, UPDATE and DELETE are
available.

The table already holds rows. They show how this table formats its values.
SELECT some before you write, and format yours to match.

Call commit_final_answer once the table holds the final answer. Signal completion
by making that tool call.
"""

SYSTEM_B = """
Call checkpoint before a modification you are unsure about, and restore to undo
everything since the most recent checkpoint. Restoring is cheap — prefer trying
an approach and undoing it over reasoning about which approach is correct.
"""

NO_ARGS = {"type": "object", "properties": {}, "required": []}


def _tool(name: str, description: str, parameters: dict = NO_ARGS) -> dict:
    """Wrap a tool definition in the OpenAI function-calling shape."""
    return {"type": "function",
            "function": {"name": name, "description": description, "parameters": parameters}}


TOOLS = {
    "execute_sql": _tool(
        "execute_sql",
        "Run one SQL statement against the table and return its result.",
        {"type": "object",
         "properties": {"sql": {"type": "string", "description": "A single SQL statement."}},
         "required": ["sql"]}),
    "commit_final_answer": _tool(
        "commit_final_answer",
        "Call when the table is in its final state and the task is complete."),
    "checkpoint": _tool(
        "checkpoint", "Record the current table state so you can return to it later."),
    "restore": _tool(
        "restore", "Undo everything since the most recent checkpoint."),
}


def tools_for(mode: str) -> list[dict]:
    """Return the tool schemas offered in this mode."""
    names = ["execute_sql", "commit_final_answer"]
    if mode == "B":
        names += ["checkpoint", "restore"]
    return [TOOLS[n] for n in names]


def system_for(mode: str) -> str:
    """Return the system prompt for this mode."""
    return SYSTEM + SYSTEM_B if mode == "B" else SYSTEM
