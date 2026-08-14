"""Milestone 0 — calibrate the scorer against the benchmark's own ground truth.

Teaching-workspace asset for lesson 02. Run it from the repo root:

    uv run python assets/milestone0.py              # default group_concat_max_len
    uv run python assets/milestone0.py 1048576      # raised
    uv run python assets/milestone0.py 64           # deliberately too small

For each of the 40 modification tasks: build a fresh single-table database, run the
gold `label` SQL, hash the final table state, compare to `answer_md5`. Anything less
than 40/40 means the *scorer* is wrong, not the SQL — and every Mode A / Mode B
number measured with it would be meaningless.

This is deliberately standalone and dependency-light so it can be read in one sitting.
Port the hashing and table-setup logic into src/dbagent/ as your own project code;
the two reusable pieces are `build_table()` and `hash_table()`.
"""
import json
import sys
import time

import pymysql

DSN = dict(host="127.0.0.1", port=3306, user="root", password="pw",
           charset="utf8mb4", autocommit=True)
DB = "m0"


def load_modification_tasks(path="data/dev.jsonl"):
    rows = [json.loads(line) for line in open(path)]
    return [r for r in rows if r["type"][0] in ("INSERT", "UPDATE")]


def build_table(cur, task):
    """Fresh database + single all-TEXT table + rows. Mirrors AgentBench's _build_init_sql.

    Every identifier is backticked: table and column names contain spaces
    ('School Location Table', 'Date moved'). All columns are TEXT, including numbers.
    """
    name = task["table"]["table_name"]
    cols = [c["name"] for c in task["table"]["table_info"]["columns"]]
    rows = task["table"]["table_info"]["rows"]

    cur.execute(f"DROP DATABASE IF EXISTS {DB}")
    cur.execute(f"CREATE DATABASE {DB}")
    cur.execute(f"USE {DB}")

    coldef = ", ".join(f"`{c}` TEXT" for c in cols)
    cur.execute(f"CREATE TABLE IF NOT EXISTS `{name}` ({coldef})")

    if rows:
        one = "(" + ", ".join(["%s"] * len(cols)) + ")"
        placeholders = ", ".join([one] * len(rows))
        colnames = ", ".join(f"`{c}`" for c in cols)
        flat = [v for r in rows for v in r]
        cur.execute(f"INSERT INTO `{name}` ({colnames}) VALUES {placeholders}", flat)

    return name, cols


def hash_table(cur, name, cols):
    """Row-order-insensitive hash of the whole table, as AgentBench computes it.

    THE TRAP: AgentBench stores `answer_md5` as str(cursor.fetchall()) from a driver
    whose fetchall() returns a LIST. pymysql returns a TUPLE. The MD5 bytes are
    identical, but "[('abc',)]" != "(('abc',),)" and all 40 tasks fail. Wrapping in
    list() is the entire fix. Compare strings; never parse the value.
    """
    concat = ", ".join(f"`{c}`" for c in cols)
    cur.execute(
        f"SELECT md5(group_concat(rowhash ORDER BY rowhash)) AS hash FROM ("
        f"  SELECT substring(MD5(CONCAT_WS(',', {concat})), 1, 5) AS rowhash"
        f"  FROM `{name}`"
        f") AS sub"
    )
    return str(list(cur.fetchall()))


def main():
    gcml = int(sys.argv[1]) if len(sys.argv) > 1 else None
    tasks = load_modification_tasks()
    conn = pymysql.connect(**DSN)

    passed, failed, timings, rowcounts = 0, [], [], []

    with conn.cursor() as cur:
        for i, task in enumerate(tasks):
            rowcounts.append(len(task["table"]["table_info"]["rows"]))
            name, cols = build_table(cur, task)
            if gcml:
                cur.execute(f"SET SESSION group_concat_max_len = {gcml}")

            t0 = time.perf_counter()
            for stmt in task["label"]:
                cur.execute(stmt)
            timings.append((time.perf_counter() - t0) * 1000)

            got, want = hash_table(cur, name, cols), task["answer_md5"]
            if got == want:
                passed += 1
            else:
                failed.append((i, task["type"][0], name, want, got))

    label = f"group_concat_max_len={gcml}" if gcml else "group_concat_max_len=default"
    print(f"Milestone 0 [{label}]: {passed}/{len(tasks)} match answer_md5")
    for i, ty, name, want, got in failed:
        print(f"  FAIL #{i} [{ty}] {name}\n    want {want}\n    got  {got}")
    print(f"rows per table: min={min(rowcounts)} max={max(rowcounts)} "
          f"— group_concat truncates above ~170 rows at 6 bytes/rowhash")
    print(f"gold SQL exec: median {sorted(timings)[len(timings) // 2]:.2f} ms")
    return 0 if passed == len(tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
