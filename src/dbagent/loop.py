"""The agent loop: one task, one mode, three possible outcomes."""

import json
import time

from . import guard
from .config import MAX_STEPS, MAX_TOKENS, MODEL
from .session import Session

SYSTEM = """You are operating on a single MySQL table to complete one task.

Use execute_sql to inspect the table and to make modifications. Only SELECT,
INSERT, UPDATE and DELETE are permitted; anything else is rejected by the
harness, so do not attempt it. When the table is in its final state, call
commit_final_answer.
"""

SYSTEM_B = """
You may checkpoint before a risky modification and restore afterwards if the
result is wrong. checkpoint records the current state; restore undoes everything
since the most recent checkpoint. Restoring is cheap — prefer trying an approach
and undoing it over reasoning about which approach is correct.
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


def dispatch(session, trace, call, response, llm_ms: float) -> tuple[str, bool]:
    """Execute one tool call, record it, and return (result for the model, done)."""
    started = time.perf_counter()
    name = call.function.name
    args = json.loads(call.function.arguments or "{}")

    if name == "execute_sql":
        sql = args["sql"]
        if not guard.is_allowed(sql):
            reason = f"rejected: only {', '.join(sorted(guard.ALLOWED))} are permitted"
            trace.step("rejected", response, depth=session.depth, sql=sql, reason=reason,
                       llm_ms=llm_ms)
            return reason, False
        session.cur.execute(sql)
        rows = session.cur.fetchall() if session.cur.description else []
        trace.step("execute_sql", response, depth=session.depth, sql=sql,
                   rowcount=session.cur.rowcount, llm_ms=llm_ms,
                   db_ms=(time.perf_counter() - started) * 1000)
        return f"{session.cur.rowcount} row(s) affected. {rows[:20]}", False

    if name in ("checkpoint", "restore"):
        getattr(session, name)()
        trace.step(name, response, depth=session.depth, llm_ms=llm_ms,
                   db_ms=(time.perf_counter() - started) * 1000)
        return f"{name} done", False

    if name == "commit_final_answer":
        trace.step("commit_final_answer", response, depth=session.depth, llm_ms=llm_ms)
        return "committed", True

    raise RuntimeError(f"model called an unknown tool: {name!r}")


def run_task(client, cur, task: dict, mode: str, trace) -> None:
    """Run one task to completion, or raise so the run stops and can be debugged."""
    session = Session(cur, mode)
    messages = [
        {"role": "system", "content": system_for(mode)},
        {"role": "user", "content": f"{task['description']}\n\n{task['add_description']}"},
    ]

    for step in range(1, MAX_STEPS + 1):
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=tools_for(mode),
            tool_choice="auto",
        )
        llm_ms = (time.perf_counter() - started) * 1000
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            trace.step("halt", response, depth=session.depth, llm_ms=llm_ms)
            raise RuntimeError(f"step {step}: finish_reason={choice.finish_reason!r}")

        calls = choice.message.tool_calls
        if len(calls) != 1:
            raise RuntimeError(f"step {step}: {len(calls)} tool calls, expected 1")

        result, done = dispatch(session, trace, calls[0], response, llm_ms)
        messages += [
            choice.message,
            {"role": "tool", "tool_call_id": calls[0].id, "content": result},
        ]
        if done:
            session.commit()
            return

    raise RuntimeError(f"{MAX_STEPS} steps without commit_final_answer — read {trace.path}")
