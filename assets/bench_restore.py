"""Measure restore cost for candidate Mode B mechanisms, on a real DBBench table.

Teaching-workspace asset for lesson 03. Run from the repo root:

    uv run python assets/bench_restore.py

Measures, on the largest of the 40 modification tables (44 rows):

  0. the round-trip floor            -- what a statement costs before doing any work
  1. SAVEPOINT                       -- checkpoint cost
  2. ROLLBACK TO SAVEPOINT           -- restore cost, 1 row dirty and all rows dirty
  3. replay-prefix                   -- reset to init + replay k accepted statements
  4. mysqldump + reload              -- logical snapshot
  5. docker commit                   -- container snapshot

THE FLOOR MUST MATCH THE SHAPE OF WHAT YOU MEASURE. An earlier version used
`SELECT 1` and got a *negative* net cost for SAVEPOINT, which is impossible.
`SELECT 1` returns a result set (row data + column metadata); SAVEPOINT returns
only an OK packet. `DO 1` is the right no-op -- it evaluates an expression and
returns an OK packet, exactly like SAVEPOINT. Same principle as a control arm:
the baseline must do the same work as the treatment, minus only the one thing
being isolated.
"""
import json
import statistics
import subprocess
import time

import pymysql

DSN = dict(host="127.0.0.1", port=3306, user="root", password="pw",
           charset="utf8mb4", autocommit=True)
DB = "bench"
FLOOR_SQL = "DO 1"  # NOT "SELECT 1" -- see module docstring


def largest_modification_task(path="data/dev.jsonl"):
    rows = [json.loads(line) for line in open(path)]
    mod = [r for r in rows if r["type"][0] in ("INSERT", "UPDATE")]
    return max(mod, key=lambda r: len(r["table"]["table_info"]["rows"]))


def report(name, samples_ms, floor=None):
    s = sorted(samples_ms)
    p50, p95 = statistics.median(s), s[int(len(s) * 0.95) - 1]
    net = f"   net {p50 - floor:8.3f}" if floor is not None else ""
    print(f"{name:<40} n={len(s):>4}  p50 {p50:9.3f} ms  p95 {p95:9.3f} ms{net}")
    return p50


def timeit(fn, n, warmup=20):
    """Warm up first: the first calls pay for connection state and page cache."""
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def main():
    task = largest_modification_task()
    name = task["table"]["table_name"]
    cols = [c["name"] for c in task["table"]["table_info"]["columns"]]
    rows = task["table"]["table_info"]["rows"]
    gold = task["label"][0]

    coldef = ", ".join(f"`{c}` TEXT" for c in cols)
    colnames = ", ".join(f"`{c}`" for c in cols)
    one = "(" + ", ".join(["%s"] * len(cols)) + ")"
    placeholders = ", ".join([one] * len(rows))
    flat = [v for r in rows for v in r]
    first = cols[0]

    print(f"table {name!r}: {len(rows)} rows x {len(cols)} cols\n")
    cur = pymysql.connect(**DSN).cursor()

    def init():
        cur.execute(f"DROP DATABASE IF EXISTS {DB}")
        cur.execute(f"CREATE DATABASE {DB}")
        cur.execute(f"USE {DB}")
        cur.execute(f"CREATE TABLE `{name}` ({coldef})")
        cur.execute(f"INSERT INTO `{name}` ({colnames}) VALUES {placeholders}", flat)

    init()

    floor = report(f"{FLOOR_SQL}  (round-trip floor)",
                   timeit(lambda: cur.execute(FLOOR_SQL), 400))
    print()

    cur.execute("START TRANSACTION")
    report("SAVEPOINT sp1  (checkpoint)",
           timeit(lambda: cur.execute("SAVEPOINT sp1"), 400), floor)

    def rollback_after(update_sql):
        """Time ONLY the rollback -- setup must not be inside the timed region."""
        cur.execute("SAVEPOINT sp1")
        cur.execute(update_sql)
        t0 = time.perf_counter()
        cur.execute("ROLLBACK TO SAVEPOINT sp1")
        return (time.perf_counter() - t0) * 1000

    for label, sql in [("1 row dirty", f"UPDATE `{name}` SET `{first}`='x' LIMIT 1"),
                       (f"{len(rows)} rows dirty", f"UPDATE `{name}` SET `{first}`='x'")]:
        for _ in range(20):
            rollback_after(sql)
        report(f"ROLLBACK TO SAVEPOINT ({label})",
               [rollback_after(sql) for _ in range(400)], floor)
    cur.execute("COMMIT")
    print()

    def replay(k):
        def f():
            init()
            for _ in range(k):
                cur.execute(gold)
        return f

    for k in (0, 1, 5, 20):
        report(f"replay-prefix restore (k={k} stmts)",
               timeit(replay(k), 40, warmup=5), floor)
    print()

    def dump_reload():
        d = subprocess.run(["docker", "exec", "dbbench-mysql", "mysqldump",
                            "-uroot", "-ppw", DB], capture_output=True)
        subprocess.run(["docker", "exec", "-i", "dbbench-mysql", "mysql",
                        "-uroot", "-ppw", DB], input=d.stdout, capture_output=True)

    report("mysqldump + reload", timeit(dump_reload, 10, warmup=2), floor)

    def docker_commit():
        subprocess.run(["docker", "commit", "dbbench-mysql", "bench-snap:tmp"],
                       capture_output=True)

    report("docker commit (snapshot only)", timeit(docker_commit, 3, warmup=1), floor)
    subprocess.run(["docker", "rmi", "-f", "bench-snap:tmp"], capture_output=True)
    cur.execute(f"DROP DATABASE IF EXISTS {DB}")


if __name__ == "__main__":
    main()
