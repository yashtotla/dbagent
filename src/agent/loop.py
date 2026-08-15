"""The agent loop: one task, one mode, three possible outcomes."""

import json
import time

from src.agent import guard
from src.agent.prompts import system_for, tools_for
from src.agent.session import Session
from src.utils.config import MAX_STEPS, MAX_TOKENS


def dispatch(session, trace, call, response, llm_ms: float | None) -> tuple[str, bool]:
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
        try:
            session.cur.execute(sql)
            rows = session.cur.fetchall() if session.cur.description else []
        except Exception as e:
            # Log before re-raising: a statement that fails is the one you most
            # need to see, and the process is about to stop.
            trace.step("execute_sql", response, depth=session.depth, sql=sql,
                       rowcount=None, db_error=f"{type(e).__name__}: {e}",
                       llm_ms=llm_ms, db_ms=(time.perf_counter() - started) * 1000)
            raise
        trace.step("execute_sql", response, depth=session.depth, sql=sql,
                   rowcount=session.cur.rowcount, db_error=None, llm_ms=llm_ms,
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


def run_task(client, cur, task: dict, mode: str, trace, model: str) -> None:
    """Run one task to completion, or raise so the run stops and can be debugged."""
    session = Session(cur, mode)
    messages = [
        {"role": "system", "content": system_for(mode)},
        {"role": "user", "content": f"{task['description']}\n\n{task['add_description']}"},
    ]

    for step in range(1, MAX_STEPS + 1):
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=tools_for(mode),
            tool_choice="auto",
        )
        llm_ms = (time.perf_counter() - started) * 1000
        choice = response.choices[0]
        calls = choice.message.tool_calls or []

        if not calls:
            trace.step("halt", response, depth=session.depth, llm_ms=llm_ms,
                       reason=f"finish_reason={choice.finish_reason!r}")
            raise RuntimeError(f"step {step}: no tool call, "
                               f"finish_reason={choice.finish_reason!r}")

        # Qwen batches calls despite parallel_tool_calls, and Mode B batches more
        # because it offers more tools. Rejecting batches would penalise Mode B
        # for its tool count. The array is ordered, so run it in order.
        messages.append(choice.message)
        done = False
        for i, call in enumerate(calls):
            try:
                result, done = dispatch(session, trace, call, response,
                                        llm_ms if i == 0 else None)
            except Exception as e:
                trace.step("halt", response, depth=session.depth, llm_ms=llm_ms,
                           reason=f"dispatch failed: {type(e).__name__}: {e}")
                raise
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            if done:
                break
        if done:
            session.commit()
            return

    raise RuntimeError(f"{MAX_STEPS} steps without commit_final_answer — read {trace.path}")
