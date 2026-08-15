"""Run tasks in one mode and print every step the agent took."""

import re

from openai import OpenAI

from src.agent.loop import run_task
from src.db.mysql import build_table, connect, drop_task_db, hash_table
from src.utils.config import MAX_STEPS, resolve_model
from src.utils.tasks import load_modification_tasks
from src.utils.trace import Trace, load


def clean(text) -> str:
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
            line += f"  -> {clean(record['reason'])[:72]}"
        print(line)


def select(limit: int, offset: int, ids: list[str] | None) -> list[dict]:
    """Return the tasks to run, by explicit id or by slice."""
    tasks = load_modification_tasks()
    if not ids:
        return tasks[offset:offset + limit]
    chosen = [t for t in tasks if t["task_id"] in set(ids)]
    # A mistyped id would silently shrink the run, and a smaller denominator is
    # the kind of wrong number that reads as a result.
    missing = set(ids) - {t["task_id"] for t in chosen}
    assert not missing, f"unknown task ids: {sorted(missing)}"
    return chosen


def main(mode: str, model: str, limit: int = 3, offset: int = 0,
         tasks: list[str] | None = None) -> int:
    """Run the selected tasks in `mode`, printing each step."""
    settings = resolve_model(model)
    client = OpenAI(api_key=settings["api_key"], base_url=settings["base_url"])
    tasks = select(limit, offset, tasks)
    conn = connect()
    passed = 0

    print(f"model: {model} ({settings['model']})   mode: {mode}   tasks: {len(tasks)}\n")
    with conn.cursor() as cur:
        for task in tasks:
            name, cols = build_table(cur, task)
            trace = Trace(task["task_id"], mode, model=model,
                          endpoint=settings["base_url"], max_steps=MAX_STEPS)
            print(f"  {task['task_id']}  {clean(task['description'])[:76]}")
            try:
                run_task(client, cur, task, mode, trace, settings["model"])
                got = hash_table(cur, name, cols)
                ok = got == task["answer_md5"]
                trace.result(passed=ok, hash_got=got, hash_want=task["answer_md5"])
                passed += ok
                show(trace.path)
                print(f"    => {'PASS' if ok else 'FAIL'}\n")
            except Exception as e:
                show(trace.path)
                print(f"    => RAISED {type(e).__name__}: {clean(e)[:76]}\n")
        drop_task_db(cur)
    conn.close()

    print(f"{passed}/{len(tasks)} passed. Traces in runs/{model}/")
    return 0
