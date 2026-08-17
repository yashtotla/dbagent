"""Measure what each candidate restore mechanism costs, on the largest DBBench table."""

import statistics
import subprocess
import time

import pymysql

from src.utils.config import DSN
from src.utils.tasks import columns, load_modification_tasks, table_name

DB = "restore_bench"

# NOT "SELECT 1". A floor must match the shape of what it measures: SELECT returns a
# result set, SAVEPOINT returns only an OK packet. Using SELECT 1 inflates the floor
# ~16% and drives the cheapest operations negative, which is impossible.
FLOOR_SQL = "DO 1"


def largest_modification_task() -> dict:
    """Return the modification task with the most rows."""
    return max(load_modification_tasks(),
               key=lambda t: len(t["table"]["table_info"]["rows"]))


def report(name: str, samples_ms: list[float], floor: float | None = None) -> float:
    """Print p50 and p95 for one mechanism and return its p50."""
    s = sorted(samples_ms)
    p50, p95 = statistics.median(s), s[int(len(s) * 0.95) - 1]
    net = f"   net {p50 - floor:8.3f}" if floor is not None else ""
    print(f"{name:<40} n={len(s):>4}  p50 {p50:9.3f} ms  p95 {p95:9.3f} ms{net}")
    return p50


def timeit(fn, n: int, warmup: int = 20) -> list[float]:
    """Time n calls, discarding a warmup that pays for connection state and page cache."""
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def main() -> None:
    """Measure every mechanism against a common floor and print the table."""
    task = largest_modification_task()
    name, cols = table_name(task), columns(task)
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
        # Setup must sit outside the timed region or it is the thing being measured.
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
