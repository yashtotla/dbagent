"""Trace capture and analysis for runs/<task_id>.<mode>.jsonl.

Teaching-workspace asset for lesson 05. Demo (synthetic data, no API calls):

    uv run python assets/trace.py

TWO LAYERS, AND THE RULE IS DIFFERENT FOR EACH
----------------------------------------------
    raw capture   ->  log everything cheap to observe.        Append-only.
    derived view  ->  compute the pre-agreed fields from raw. Pure function.

Capture maximally. An extra field costs bytes; a missing one costs a re-run --
a day and a slice of API budget. At 40 tasks x 2 modes x ~10 steps this file
holds ~800 records, so there is no scale at which curation pays for itself.

Derive narrowly. `summarize()` and `compare_modes()` produce the agreed fields
and nothing else, so the analysis stays legible. Because they are pure functions
of the raw log, a question you think of *after* the run is recomputable rather
than lost -- which is the whole point of keeping the layers separate.

WHAT THE BACKWARDS CHECK IS ACTUALLY FOR
----------------------------------------
Enumerating the write-up's claims does NOT tell you what to capture (capture
everything). It tells you what must be *decided or arranged* before the run,
because no amount of logging can recover it afterwards:

    mode label          -- nothing in an API response says "this was arm B"
    scorer verdict      -- pass/fail exists only if you run the scorer and write it down
    held-fixed config   -- "we held effort fixed" is unprovable unless effort is in the header
    prompt identity     -- a hash, captured per run, or you cannot show the prompt never drifted

Those four are design commitments. Everything else is just capture.

THINGS EASY TO MISS, AND WHY THEY MATTER HERE
---------------------------------------------
    stop_reason  -- a run truncated at max_tokens is a HARNESS artifact, not an
                    agent failure. Mode B takes more steps -> more tokens -> more
                    likely to truncate. Without this field that confound is
                    invisible and scores as a research result.
    usage        -- an entire cost axis
    content      -- the agent's stated reasoning between tool calls is where
                    "why did it restore?" lives
    db_error     -- the driver's verbatim error, not a summarized reason string
"""
import hashlib
import json
import time
from pathlib import Path

EVENTS = ("execute_sql", "rejected", "checkpoint", "restore", "commit_final_answer")


def sha(obj):
    """Stable hash of a prompt or tool schema, for proving it never drifted."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]


# --------------------------------------------------------------------------
# Layer 1 — raw capture. Write everything; interpret nothing.
# --------------------------------------------------------------------------

class TraceWriter:
    def __init__(self, run_dir, task_id, mode, *, system, tools, **config):
        self.path = Path(run_dir) / f"{task_id}.{mode}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.path.open("w")
        self.task_id, self.mode, self.n = task_id, mode, 0
        self._emit({
            "type": "run", "task_id": task_id, "mode": mode,
            # design commitments — unrecoverable after the fact
            "system_sha": sha(system), "tools_sha": sha(tools),
            "system": system, "tools": tools,
            **config,
        })

    def _emit(self, rec):
        self.f.write(json.dumps(rec, default=str) + "\n")
        self.f.flush()  # a crashed run must still leave an analysable prefix

    def step(self, event, *, response=None, llm_ms=None, db_ms=None, depth=None,
             **observed):
        """One agent turn. Pass the whole API response; we keep all of it.

        `observed` is whatever else the harness saw -- sql, rowcount, db_error,
        db_warnings, reason. Add fields freely; nothing downstream breaks.
        """
        self.n += 1
        rec = {"type": "step", "n": self.n, "ts": time.time(), "event": event,
               "llm_ms": llm_ms, "db_ms": db_ms, "depth": depth, **observed}
        if response is not None:
            rec["stop_reason"] = getattr(response, "stop_reason", None)
            usage = getattr(response, "usage", None)
            rec["usage"] = usage if isinstance(usage, dict) else (
                usage.__dict__ if usage else None)
            content = getattr(response, "content", None)
            rec["content"] = content if isinstance(content, list) else (
                [b.__dict__ for b in content] if content else None)
        self._emit(rec)

    def result(self, *, passed, hash_got, hash_want, error=None):
        self._emit({"type": "result", "task_id": self.task_id, "mode": self.mode,
                    "passed": passed, "steps_used": self.n, "error": error,
                    "hash_got": hash_got, "hash_want": hash_want})
        self.f.close()


# --------------------------------------------------------------------------
# Layer 2 — derived view. Pure functions of the raw log; recompute freely.
# --------------------------------------------------------------------------

def load(path):
    return [json.loads(line) for line in Path(path).open()]


def summarize(records):
    run = next(r for r in records if r["type"] == "run")
    steps = [r for r in records if r["type"] == "step"]
    result = next((r for r in records if r["type"] == "result"), None)
    depths = [s["depth"] for s in steps if s.get("depth") is not None]
    usages = [s["usage"] for s in steps if s.get("usage")]
    return {
        "task_id": run["task_id"], "mode": run["mode"],
        "passed": result["passed"] if result else None,
        "complete": result is not None,          # False => crashed mid-run
        "steps_used": len(steps),
        "checkpoints": sum(s["event"] == "checkpoint" for s in steps),
        "restores": sum(s["event"] == "restore" for s in steps),
        "rejections": sum(s["event"] == "rejected" for s in steps),
        "max_depth": max(depths, default=0),
        # a truncated run is a harness artifact, NOT an agent failure
        "truncated": any(s.get("stop_reason") == "max_tokens" for s in steps),
        "refused": any(s.get("stop_reason") == "refusal" for s in steps),
        "db_errors": sum(bool(s.get("db_error")) for s in steps),
        "llm_ms": sum(s.get("llm_ms") or 0 for s in steps),
        "db_ms": round(sum(s.get("db_ms") or 0 for s in steps), 3),
        "in_tok": sum(u.get("input_tokens", 0) for u in usages),
        "out_tok": sum(u.get("output_tokens", 0) for u in usages),
        "system_sha": run.get("system_sha"), "tools_sha": run.get("tools_sha"),
    }


def compare_modes(summaries):
    """The deliverable's question — with harness artifacts excluded, not scored."""
    usable = [s for s in summaries if s["complete"] and not s["truncated"]
              and not s["refused"]]
    dropped = [(s["task_id"], s["mode"]) for s in summaries if s not in usable]
    by_task = {}
    for s in usable:
        by_task.setdefault(s["task_id"], {})[s["mode"]] = s
    paired = {t: m for t, m in by_task.items() if "A" in m and "B" in m}
    b = sorted(t for t, m in paired.items() if m["B"]["passed"] and not m["A"]["passed"])
    a = sorted(t for t, m in paired.items() if m["A"]["passed"] and not m["B"]["passed"])
    return {"b_recovered": b, "a_only": a, "discordant": len(b) + len(a),
            "paired_tasks": len(paired), "dropped_as_artifacts": dropped}


def check_controls(summaries):
    """Prove the held-fixed config never drifted. Per mode, one sha each."""
    out = {}
    for s in summaries:
        out.setdefault(s["mode"], set()).add((s["system_sha"], s["tools_sha"]))
    return {m: ("stable" if len(v) == 1 else f"DRIFTED — {len(v)} variants")
            for m, v in out.items()}


def narrate(records):
    """One task's branch structure, including what the agent said between calls."""
    out = []
    for r in records:
        if r["type"] != "step":
            continue
        said = ""
        for blk in (r.get("content") or []):
            if blk.get("type") == "text" and blk.get("text", "").strip():
                said = f'\n         "{blk["text"].strip()[:72]}"'
        e = r["event"]
        if e == "execute_sql":
            head = f"ran      {r.get('sql', '')[:50]}  (rows={r.get('rowcount')})"
        elif e == "rejected":
            head = f"REJECTED {r.get('sql', '')[:42]} — {r.get('reason', '')[:26]}"
        elif e in ("checkpoint", "restore"):
            head = f"{e.upper():<8} -> depth {r.get('depth')}"
        else:
            head = e
        out.append(f"  {r['n']:>2}. {head}{said}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Demo — SYNTHETIC. No model was called. Shows the schema is sufficient.
# --------------------------------------------------------------------------

class _Resp:
    """Stand-in for an anthropic Message."""
    def __init__(self, stop_reason, in_tok, out_tok, text=None, tool=None):
        self.stop_reason = stop_reason
        self.usage = {"input_tokens": in_tok, "output_tokens": out_tok,
                      "cache_read_input_tokens": 0}
        self.content = ([{"type": "text", "text": text}] if text else []) + \
                       ([{"type": "tool_use", "name": tool}] if tool else [])


def _demo(run_dir="/tmp/dbagent-trace-demo"):
    SYS, TOOLS = "You are a database agent...", [{"name": "execute_sql"}]
    cfg = dict(system=SYS, tools=TOOLS, model="claude-opus-5", effort="high",
               thinking="adaptive", disable_parallel_tool_use=True, max_steps=30,
               guard="allowlist-v1")
    WANT, WRONG = "[('6e5be...',)]", "[('0e954...',)]"

    a = TraceWriter(run_dir, "task_19", "A", **cfg)
    a.step("execute_sql", llm_ms=2100, db_ms=0.42,
           response=_Resp("tool_use", 3200, 74, "Updating the Rams row.", "execute_sql"),
           sql="UPDATE `Statistics` SET `Wins`='12' WHERE `Team`='Rams'", rowcount=3)
    a.step("commit_final_answer", llm_ms=1800, db_ms=0.15,
           response=_Resp("tool_use", 3350, 30, tool="commit_final_answer"))
    a.result(passed=False, hash_got=WRONG, hash_want=WANT)

    b = TraceWriter(run_dir, "task_19", "B", **cfg)
    b.step("checkpoint", llm_ms=1950, db_ms=0.10, depth=1,
           response=_Resp("tool_use", 3400, 42, "Checkpointing before I try this.", "checkpoint"))
    b.step("execute_sql", llm_ms=2300, db_ms=0.44, depth=1,
           response=_Resp("tool_use", 3520, 80, tool="execute_sql"),
           sql="UPDATE `Statistics` SET `Wins`='12' WHERE `Team`='Rams'", rowcount=3)
    b.step("execute_sql", llm_ms=2050, db_ms=0.28, depth=1,
           response=_Resp("tool_use", 3610, 66,
                          "Three rows changed — I expected one. Checking.", "execute_sql"),
           sql="SELECT * FROM `Statistics` WHERE `Team`='Rams'", rowcount=3)
    b.step("restore", llm_ms=2400, db_ms=0.66, depth=1,
           response=_Resp("tool_use", 3700, 58,
                          "Wrong — the predicate is too broad. Undoing.", "restore"))
    b.step("rejected", llm_ms=1900, depth=1,
           response=_Resp("tool_use", 3760, 48, tool="execute_sql"),
           sql="CREATE INDEX idx ON `Statistics` (`Team`(8))",
           reason="rejected: CREATE is not permitted")
    b.step("execute_sql", llm_ms=2200, db_ms=0.39, depth=1,
           response=_Resp("tool_use", 3840, 92,
                          "Adding Year to the predicate.", "execute_sql"),
           sql="UPDATE `Statistics` SET `Wins`='12' WHERE `Team`='Rams' AND `Year`='2019'",
           rowcount=1)
    b.step("commit_final_answer", llm_ms=1700, db_ms=0.14, depth=1,
           response=_Resp("tool_use", 3900, 28, tool="commit_final_answer"))
    b.result(passed=True, hash_got=WANT, hash_want=WANT)

    for mode in ("A", "B"):
        w = TraceWriter(run_dir, "task_04", mode, **cfg)
        w.step("execute_sql", llm_ms=2000, db_ms=0.31,
               response=_Resp("tool_use", 3100, 70, tool="execute_sql"),
               sql="INSERT INTO `Golf Tournament Winners` VALUES (...)", rowcount=1)
        w.step("commit_final_answer", llm_ms=1750, db_ms=0.12,
               response=_Resp("tool_use", 3180, 26, tool="commit_final_answer"))
        w.result(passed=True, hash_got=WANT, hash_want=WANT)

    # task_31 Mode B truncates. Without stop_reason this scores as an agent failure.
    t = TraceWriter(run_dir, "task_31", "B", **cfg)
    t.step("execute_sql", llm_ms=2400, db_ms=0.35, depth=0,
           response=_Resp("max_tokens", 4100, 4096, tool="execute_sql"),
           sql="UPDATE `Locomotive Inventory Table` SET ...", rowcount=0)
    t.result(passed=False, hash_got=WRONG, hash_want=WANT)
    u = TraceWriter(run_dir, "task_31", "A", **cfg)
    u.step("execute_sql", llm_ms=2000, db_ms=0.30,
           response=_Resp("tool_use", 3050, 61, tool="execute_sql"),
           sql="UPDATE `Locomotive Inventory Table` SET ...", rowcount=1)
    u.result(passed=True, hash_got=WANT, hash_want=WANT)

    summaries = [summarize(load(p)) for p in sorted(Path(run_dir).glob("*.jsonl"))]

    print("SYNTHETIC DEMO — no model was called.\n")
    cols = ("task_id", "mode", "passed", "steps_used", "checkpoints", "restores",
            "rejections", "max_depth", "truncated", "llm_ms", "db_ms", "out_tok")
    w_ = [9, 5, 6, 6, 5, 5, 4, 6, 10, 8, 7, 8]
    print("".join(c[:x - 1].ljust(x) for c, x in zip(cols, w_)))
    print("-" * sum(w_))
    for s in summaries:
        print("".join(str(s[c]).ljust(x) for c, x in zip(cols, w_)))

    print("\ncontrols:", check_controls(summaries))
    cmp = compare_modes(summaries)
    print(f"paired: {cmp['paired_tasks']}   discordant: {cmp['discordant']}")
    print(f"dropped as harness artifacts: {cmp['dropped_as_artifacts']}")
    print(f"\nCheckpointing recovered: {cmp['b_recovered'] or 'none'}")
    print(f"Mode A won where B lost:  {cmp['a_only'] or 'none'}")
    print("  ^ task_31 is NOT here: Mode B truncated at max_tokens, so it is a")
    print("    harness artifact. Without stop_reason it would read as a real loss.")

    print(f"\nNamed case — task_19, Mode B:\n{narrate(load(Path(run_dir) / 'task_19.B.jsonl'))}")


if __name__ == "__main__":
    _demo()
