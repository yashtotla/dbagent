"""Trace writer and analyser for runs/<task_id>.jsonl.

Teaching-workspace asset for lesson 05. Demo (synthetic data, no API calls):

    uv run python assets/trace.py

THE DESIGN RULE
---------------
A trace is a commitment about which questions you will be able to answer. Any
field you don't log is a question you have silently declined. You find out which
ones at analysis time, when re-running costs another day of API budget.

So the schema below was derived BACKWARDS from the sentences the write-up has to
support, not forwards from what is easy to log:

  "Mode B recovered tasks 7, 19 and 31; Mode A did not."   -> task_id, mode, passed
  "Checkpointing enabled recovery in case 19: the agent
   tried X, saw the row count was wrong, restored, tried Y" -> ordered events + depth
  "Mode B explored 2.3 branches per task, Mode A 1.0."      -> checkpoint/restore events
  "Multi-level backtracking never bound."                   -> max_depth per task
  "The guard cost no reachable score."                      -> rejection events
  "Mechanism cost was 0.01% of a turn."                     -> db_ms AND llm_ms per step
  "Both modes had equal productive step budgets."           -> steps_used, rejections, per mode
  "Model, effort and thinking were held fixed."             -> run header

CLAUDE.md specifies `(step, sql, response, latency)`. That covers the third
column of a Mode A loop and cannot express a checkpoint, a restore, a rejection,
a mode, or a pass/fail — so it cannot answer the deliverable's own question.
"""
import json
import time
from pathlib import Path


class TraceWriter:
    """One file per (task, mode). Header first, steps, then a result line."""

    def __init__(self, run_dir, task_id, mode, config):
        self.path = Path(run_dir) / f"{task_id}.{mode}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.path.open("w")
        self.task_id, self.mode, self.n = task_id, mode, 0
        self._emit({"type": "run", "task_id": task_id, "mode": mode, **config})

    def _emit(self, rec):
        self.f.write(json.dumps(rec) + "\n")
        self.f.flush()  # a crashed run must still leave an analysable prefix

    def step(self, event, *, llm_ms, db_ms=None, depth=None, **fields):
        """One agent turn. `event` is what the agent did, not what SQL ran.

        event ∈ execute_sql | rejected | checkpoint | restore | commit_final_answer
        """
        self.n += 1
        self._emit({"type": "step", "n": self.n, "event": event,
                    "llm_ms": llm_ms, "db_ms": db_ms, "depth": depth, **fields})

    def result(self, *, passed, hash_got, hash_want):
        self._emit({"type": "result", "task_id": self.task_id, "mode": self.mode,
                    "passed": passed, "steps_used": self.n,
                    "hash_got": hash_got, "hash_want": hash_want})
        self.f.close()


# --------------------------------------------------------------------------
# Analysis — every function here answers one sentence in the write-up.
# --------------------------------------------------------------------------

def load(path):
    return [json.loads(line) for line in Path(path).open()]


def summarize(records):
    """Per-run counters. Derived, never stored — the events are the source."""
    run = next(r for r in records if r["type"] == "run")
    steps = [r for r in records if r["type"] == "step"]
    result = next((r for r in records if r["type"] == "result"), None)
    depths = [s["depth"] for s in steps if s.get("depth") is not None]
    return {
        "task_id": run["task_id"],
        "mode": run["mode"],
        "passed": result["passed"] if result else None,
        "steps_used": len(steps),
        "checkpoints": sum(s["event"] == "checkpoint" for s in steps),
        "restores": sum(s["event"] == "restore" for s in steps),
        "rejections": sum(s["event"] == "rejected" for s in steps),
        "max_depth": max(depths, default=0),
        "llm_ms": sum(s.get("llm_ms") or 0 for s in steps),
        "db_ms": round(sum(s.get("db_ms") or 0 for s in steps), 3),
    }


def compare_modes(summaries):
    """The deliverable's question: which specific tasks did checkpointing rescue?"""
    by_task = {}
    for s in summaries:
        by_task.setdefault(s["task_id"], {})[s["mode"]] = s
    b_wins = sorted(t for t, m in by_task.items()
                    if "A" in m and "B" in m and m["B"]["passed"] and not m["A"]["passed"])
    a_wins = sorted(t for t, m in by_task.items()
                    if "A" in m and "B" in m and m["A"]["passed"] and not m["B"]["passed"])
    return {"b_recovered": b_wins, "a_only": a_wins,
            "discordant": len(b_wins) + len(a_wins), "paired_tasks": len(by_task)}


def narrate(records):
    """Reconstruct one task's branch structure — the named-case paragraph."""
    out = []
    for r in records:
        if r["type"] != "step":
            continue
        e, d = r["event"], r.get("depth")
        if e == "execute_sql":
            out.append(f"  {r['n']:>2}. ran     {r.get('sql', '')[:52]}"
                       f"  (rows={r.get('rowcount')})")
        elif e == "rejected":
            out.append(f"  {r['n']:>2}. REJECTED {r.get('sql', '')[:44]}  — {r.get('reason', '')[:30]}")
        elif e == "checkpoint":
            out.append(f"  {r['n']:>2}. checkpoint -> depth {d}")
        elif e == "restore":
            out.append(f"  {r['n']:>2}. RESTORE    -> depth {d}   (undid the previous attempt)")
        elif e == "commit_final_answer":
            out.append(f"  {r['n']:>2}. commit")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Demo — SYNTHETIC data. No API calls, no model was run to produce this.
# It exists to show the schema is sufficient, not to report a result.
# --------------------------------------------------------------------------

def _demo(run_dir="/tmp/dbagent-trace-demo"):
    cfg = {"model": "claude-opus-5", "effort": "high", "thinking": "adaptive",
           "disable_parallel_tool_use": True, "max_steps": 30, "guard": "allowlist-v1"}
    WANT = "[('6e5be5df6a81c825cba000c75965d27f',)]"
    WRONG = "[('0e954e950043683e9817dd4302d26046',)]"

    # task 19 — Mode A: one shot, wrong, unrecoverable.
    a = TraceWriter(run_dir, "task_19", "A", cfg)
    a.step("execute_sql", llm_ms=2100, db_ms=0.42,
           sql="UPDATE `Statistics` SET `Wins`='12' WHERE `Team`='Rams'", rowcount=3)
    a.step("commit_final_answer", llm_ms=1800, db_ms=0.15)
    a.result(passed=False, hash_got=WRONG, hash_want=WANT)

    # task 19 — Mode B: same first guess, notices rowcount=3, restores, corrects.
    b = TraceWriter(run_dir, "task_19", "B", cfg)
    b.step("checkpoint", llm_ms=1950, db_ms=0.10, depth=1)
    b.step("execute_sql", llm_ms=2300, db_ms=0.44, depth=1,
           sql="UPDATE `Statistics` SET `Wins`='12' WHERE `Team`='Rams'", rowcount=3)
    b.step("execute_sql", llm_ms=2050, db_ms=0.28, depth=1,
           sql="SELECT * FROM `Statistics` WHERE `Team`='Rams'", rowcount=3)
    b.step("restore", llm_ms=2400, db_ms=0.66, depth=1)
    b.step("rejected", llm_ms=1900, depth=1,
           sql="CREATE INDEX idx ON `Statistics` (`Team`(8))",
           reason="rejected: CREATE is not permitted")
    b.step("execute_sql", llm_ms=2200, db_ms=0.39, depth=1,
           sql="UPDATE `Statistics` SET `Wins`='12' WHERE `Team`='Rams' AND `Year`='2019'",
           rowcount=1)
    b.step("commit_final_answer", llm_ms=1700, db_ms=0.14, depth=1)
    b.result(passed=True, hash_got=WANT, hash_want=WANT)

    # task 04 — both modes pass. Concordant, so it carries no signal.
    for mode in ("A", "B"):
        w = TraceWriter(run_dir, "task_04", mode, cfg)
        w.step("execute_sql", llm_ms=2000, db_ms=0.31,
               sql="INSERT INTO `Golf Tournament Winners` VALUES (...)", rowcount=1)
        w.step("commit_final_answer", llm_ms=1750, db_ms=0.12)
        w.result(passed=True, hash_got=WANT, hash_want=WANT)

    summaries = [summarize(load(p)) for p in sorted(Path(run_dir).glob("*.jsonl"))]

    print("SYNTHETIC DEMO — no model was called to produce this.\n")
    hdr = f"{'task':<9}{'mode':<6}{'pass':<6}{'steps':>6}{'ckpt':>6}{'rest':>6}{'rej':>5}{'depth':>7}{'llm_ms':>9}{'db_ms':>8}"
    print(hdr); print("-" * len(hdr))
    for s in summaries:
        print(f"{s['task_id']:<9}{s['mode']:<6}{str(s['passed']):<6}{s['steps_used']:>6}"
              f"{s['checkpoints']:>6}{s['restores']:>6}{s['rejections']:>5}"
              f"{s['max_depth']:>7}{s['llm_ms']:>9}{s['db_ms']:>8}")

    cmp = compare_modes(summaries)
    print(f"\nPaired tasks: {cmp['paired_tasks']}   discordant: {cmp['discordant']}")
    print(f"Checkpointing recovered: {cmp['b_recovered'] or 'none'}")
    print(f"Mode A won where B lost:  {cmp['a_only'] or 'none'}")

    tot_llm = sum(s["llm_ms"] for s in summaries)
    tot_db = sum(s["db_ms"] for s in summaries)
    print(f"\nMechanism share of wall clock: {tot_db:.2f} ms db / {tot_llm} ms llm "
          f"= {100 * tot_db / tot_llm:.4f}%")

    print(f"\nNamed case — task_19, Mode B:\n{narrate(load(Path(run_dir) / 'task_19.B.jsonl'))}")


if __name__ == "__main__":
    _demo()
