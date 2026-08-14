"""The agent loop: one task, one mode, three possible outcomes."""

import time

from . import guard
from .config import EFFORT, MAX_STEPS, MAX_TOKENS, MODEL
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

NO_ARGS = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}

TOOLS = {
    "execute_sql": {
        "name": "execute_sql",
        "description": "Run one SQL statement against the table and return its result.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "A single SQL statement."}},
            "required": ["sql"],
            "additionalProperties": False,
        },
    },
    "commit_final_answer": {
        "name": "commit_final_answer",
        "description": "Call when the table is in its final state and the task is complete.",
        "strict": True,
        "input_schema": NO_ARGS,
    },
    "checkpoint": {
        "name": "checkpoint",
        "description": "Record the current table state so you can return to it later.",
        "strict": True,
        "input_schema": NO_ARGS,
    },
    "restore": {
        "name": "restore",
        "description": "Undo everything since the most recent checkpoint.",
        "strict": True,
        "input_schema": NO_ARGS,
    },
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
    """Execute one tool call, record it, and return (result for the agent, done)."""
    started = time.perf_counter()

    if call.name == "execute_sql":
        sql = call.input["sql"]
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

    if call.name in ("checkpoint", "restore"):
        getattr(session, call.name)()
        trace.step(call.name, response, depth=session.depth, llm_ms=llm_ms,
                   db_ms=(time.perf_counter() - started) * 1000)
        return f"{call.name} done", False

    if call.name == "commit_final_answer":
        trace.step("commit_final_answer", response, depth=session.depth, llm_ms=llm_ms)
        return "committed", True

    raise RuntimeError(f"model called an unknown tool: {call.name!r}")


def run_task(client, cur, task: dict, mode: str, trace) -> None:
    """Run one task to completion, or raise so the run stops and can be debugged."""
    session = Session(cur, mode)
    messages = [{"role": "user",
                 "content": f"{task['description']}\n\n{task['add_description']}"}]

    for step in range(1, MAX_STEPS + 1):
        started = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_for(mode),
            tools=tools_for(mode),
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            messages=messages,
        )
        llm_ms = (time.perf_counter() - started) * 1000

        if response.stop_reason != "tool_use":
            trace.step("halt", response, depth=session.depth, llm_ms=llm_ms)
            raise RuntimeError(f"step {step}: stop_reason={response.stop_reason!r}")

        calls = [b for b in response.content if b.type == "tool_use"]
        if len(calls) != 1:
            raise RuntimeError(f"step {step}: {len(calls)} tool calls, expected 1")

        result, done = dispatch(session, trace, calls[0], response, llm_ms)
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": [{"type": "tool_result",
                                          "tool_use_id": calls[0].id,
                                          "content": result}]},
        ]
        if done:
            session.commit()
            return

    raise RuntimeError(f"{MAX_STEPS} steps without commit_final_answer — read {trace.path}")
