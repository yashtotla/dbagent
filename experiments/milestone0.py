"""Verify the scorer against the benchmark's ground truth before measuring anything."""

import statistics
import time

from dbagent.db import build_table, connect, drop_task_db, hash_table
from dbagent.tasks import load_modification_tasks

# group_concat truncates around 170 rowhashes, silently returning a wrong hash.
MAX_SAFE_ROWS = 170


def main() -> int:
    """Run each task's gold SQL and compare the hash to answer_md5."""
    tasks = load_modification_tasks()
    conn = connect()
    passed, failed, timings, rowcounts = 0, [], [], []

    with conn.cursor() as cur:
        for task in tasks:
            name, cols = build_table(cur, task)
            rowcounts.append(len(task["table"]["table_info"]["rows"]))

            started = time.perf_counter()
            for stmt in task["label"]:
                cur.execute(stmt)
            timings.append((time.perf_counter() - started) * 1000)

            got, want = hash_table(cur, name, cols), task["answer_md5"]
            if got == want:
                passed += 1
            else:
                failed.append((task["task_id"], task["type"][0], name, want, got))

        drop_task_db(cur)
    conn.close()

    assert max(rowcounts) < MAX_SAFE_ROWS, (
        f"largest table is {max(rowcounts)} rows — group_concat may truncate the hash"
    )

    print(f"Milestone 0: {passed}/{len(tasks)} match answer_md5")
    for task_id, kind, name, want, got in failed:
        print(f"  FAIL {task_id} [{kind}] {name}\n    want {want}\n    got  {got}")
    print(f"rows per table: min={min(rowcounts)} max={max(rowcounts)}")
    print(f"gold SQL exec: median {statistics.median(timings):.2f} ms")

    return 0 if passed == len(tasks) else 1
