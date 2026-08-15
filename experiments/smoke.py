"""Run a few tasks in one mode and print every step, for judging a model."""

import os
import re

from openai import OpenAI

from dbagent.config import API_KEY_VAR, BASE_URL, MODEL
from dbagent.db import build_table, connect, drop_task_db, hash_table
from dbagent.tasks import load_modification_tasks
from dbagent.trace import Trace, load
import dbagent.loop as agent


def clean(text: str) -> str:
    """Strip control characters that would garble the terminal."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(text))


def show(trace_path) -> None:
    """Print each step the agent took."""
    for record in load(trace_path):
        if record["type"] != "step":
            continue
        line = f"    {record['n']:>2}. {record['event']:<20}"
        if record.get("sql"):
            line += f" {clean(record['sql'])[:72]}"
        if record.get("db_error"):
            line += f"\n        db_error: {clean(record['db_error'])[:88]}"
        elif record.get("rowcount") is not None:
            line += f"  -> {record['rowcount']} row(s)"
        if record.get("reason"):
            line += f"  -> {record['reason']}"
        print(line)


def main(limit: int = 3, offset: int = 0, mode: str = "A",
         model: str | None = None) -> int:
    """Run `limit` tasks from `offset` in `mode`, printing each step."""
    agent.MODEL = model or MODEL
    client = OpenAI(api_key=os.environ[API_KEY_VAR], base_url=BASE_URL)
    tasks = load_modification_tasks()[offset:offset + limit]
    conn = connect()
    passed = 0

    print(f"model: {agent.MODEL}   mode: {mode}   tasks: {len(tasks)}\n")
    with conn.cursor() as cur:
        for task in tasks:
            name, cols = build_table(cur, task)
            trace = Trace(task["task_id"], mode, model=agent.MODEL, max_steps=agent.MAX_STEPS)
            print(f"  {task['task_id']}  {clean(task['description'])[:76]}")
            try:
                agent.run_task(client, cur, task, mode, trace)
                ok = hash_table(cur, name, cols) == task["answer_md5"]
                trace.result(passed=ok, hash_got="", hash_want="")
                passed += ok
                show(trace.path)
                print(f"    => {'PASS' if ok else 'FAIL'}\n")
            except Exception as e:
                show(trace.path)
                print(f"    => RAISED {type(e).__name__}: {clean(e)[:76]}\n")
        drop_task_db(cur)
    conn.close()

    print(f"{passed}/{len(tasks)} passed. Traces in runs/")
    return 0
