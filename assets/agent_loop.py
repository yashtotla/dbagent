"""The agent loop, with the boundaries that actually decide the experiment.

Teaching-workspace asset for lesson 06. Exercise every exit path without an API
key or a dollar of budget:

    uv run python assets/agent_loop.py

THE LOOP IS FIVE LINES. THE BOUNDARIES ARE THE EXPERIMENT.
----------------------------------------------------------
Same shape as a database migration: the body is trivial SQL, and what breaks it
is the transaction wrapper, the half-way failure, and whether you verified after
or before. Here the equivalents are setup ordering, exit paths, and scoring point.

PER-TASK ORDERING -- each line is forced by something already established
------------------------------------------------------------------------
    1. DROP/CREATE DATABASE, CREATE TABLE, INSERT rows
         DDL causes an implicit commit, so it MUST precede START TRANSACTION
         or it destroys the savepoint (Reference 01).
    2. Mode B only: START TRANSACTION; SAVEPOINT sp_0
         sp_0 is the restore floor -- it gives the agent "reset to the start"
         without ever needing a bare ROLLBACK (Reference 05).
    3. the loop
    4. commit, then score ON THE SAME CONNECTION
    5. DROP DATABASE

EXIT PATHS -- there are six, and confounds hide in four of them
---------------------------------------------------------------
    commit_final_answer  normal. Commit, score.
    max_steps            COMMIT, do not roll back. Mode A's partial work is
                         already committed; discarding Mode B's would score the
                         two arms under different rules.
    stop_reason=max_tokens   harness artifact -> exclude from the comparison.
                         Directional: Mode B takes more steps, so it truncates
                         more often (lesson 05).
    stop_reason=refusal      harness artifact -> exclude.
    stop_reason=end_turn     model stopped without calling a tool. Reprompt ONCE,
                         then give up. Never spin.
    exception            mark incomplete; excluded, never scored as a failure.

Only the first two are scored. The other four are reported separately, because a
silent exclusion is the same failure as a silent inclusion.
"""
import time

import sql_guard
import trace as tracing

MAX_STEPS = 30
SYSTEM = """You are operating on a single MySQL table to complete one task.

Use execute_sql to inspect the table and to make modifications. Only SELECT,
INSERT, UPDATE, DELETE, SHOW, DESCRIBE and EXPLAIN are permitted; DDL and
transaction-control statements are rejected by the harness, so do not attempt
them. When the table is in its final state, call commit_final_answer.
"""
SYSTEM_B_EXTRA = """
You may checkpoint before a risky modification and restore afterwards if the
result is wrong. checkpoint() records the current state; restore() returns to the
most recent checkpoint. Restoring is cheap -- prefer trying an approach and
undoing it over reasoning about which approach is correct.
"""

EXECUTE_SQL = {
    "name": "execute_sql",
    "description": (
        "Run one SQL statement against the task's table and return its result. "
        "Call this to inspect state or to make a modification."),
    "strict": True,
    "input_schema": {"type": "object", "additionalProperties": False,
                     "required": ["sql"],
                     "properties": {"sql": {"type": "string",
                                            "description": "A single SQL statement."}}},
}
COMMIT_FINAL = {
    "name": "commit_final_answer",
    "description": "Call when the table is in its final state and the task is complete.",
    "strict": True,
    "input_schema": {"type": "object", "additionalProperties": False, "properties": {},
                     "required": []},
}
CHECKPOINT = {
    "name": "checkpoint",
    "description": "Record the current table state so you can return to it later.",
    "strict": True,
    "input_schema": {"type": "object", "additionalProperties": False, "properties": {},
                     "required": []},
}
RESTORE = {
    "name": "restore",
    "description": "Undo everything since the most recent checkpoint.",
    "strict": True,
    "input_schema": {"type": "object", "additionalProperties": False, "properties": {},
                     "required": []},
}


def tools_for(mode):
    # NOTE: Mode B carries two extra tools and a longer system prompt. That
    # confound is unavoidable by construction -- state it and measure the policy
    # change (branches per task), do not try to net it out. See Reference 02.
    return [EXECUTE_SQL, COMMIT_FINAL] + ([CHECKPOINT, RESTORE] if mode == "B" else [])


def system_for(mode):
    return SYSTEM + (SYSTEM_B_EXTRA if mode == "B" else "")


class Session:
    """Owns the transaction and the savepoint stack. The agent never sees SQL
    for checkpoint/restore -- it calls tools, the harness issues statements."""

    def __init__(self, cur, mode):
        self.cur, self.mode, self.depth = cur, mode, 0
        if mode == "B":
            cur.execute("START TRANSACTION")
            cur.execute("SAVEPOINT sp_0")   # restore floor

    def checkpoint(self):
        self.depth += 1
        self.cur.execute(f"SAVEPOINT sp_{self.depth}")
        return f"checkpoint recorded (depth {self.depth})"

    def restore(self):
        # Roll back to the most recent checkpoint and KEEP it, so retrying a
        # second alternative at the same decision point is one call.
        self.cur.execute(f"ROLLBACK TO SAVEPOINT sp_{self.depth}")
        return f"restored to checkpoint (depth {self.depth})"

    def finish(self):
        if self.mode == "B":
            self.cur.execute("COMMIT")


def dispatch(session, name, args, tw, *, llm_ms, response):
    """Execute one tool call. Every path writes exactly one trace step."""
    cur = session.cur
    t0 = time.perf_counter()

    if name == "execute_sql":
        sql = args["sql"]
        reason = sql_guard.check(sql)                    # the enforcement point
        if reason:
            tw.step("rejected", response=response, llm_ms=llm_ms,
                    depth=session.depth, sql=sql, reason=reason)
            return reason, False
        try:
            cur.execute(sql)
            rows = cur.fetchall() if cur.description else []
            db_ms = (time.perf_counter() - t0) * 1000
            tw.step("execute_sql", response=response, llm_ms=llm_ms, db_ms=db_ms,
                    depth=session.depth, sql=sql, rowcount=cur.rowcount,
                    db_error=None)
            return f"{cur.rowcount} row(s) affected. {rows[:20]}", False
        except Exception as e:                            # driver error, verbatim
            db_ms = (time.perf_counter() - t0) * 1000
            tw.step("execute_sql", response=response, llm_ms=llm_ms, db_ms=db_ms,
                    depth=session.depth, sql=sql, rowcount=None,
                    db_error=f"{type(e).__name__}: {e}")
            return f"error: {e}", False

    if name == "checkpoint":
        out = session.checkpoint()
        tw.step("checkpoint", response=response, llm_ms=llm_ms,
                db_ms=(time.perf_counter() - t0) * 1000, depth=session.depth)
        return out, False

    if name == "restore":
        out = session.restore()
        tw.step("restore", response=response, llm_ms=llm_ms,
                db_ms=(time.perf_counter() - t0) * 1000, depth=session.depth)
        return out, False

    if name == "commit_final_answer":
        tw.step("commit_final_answer", response=response, llm_ms=llm_ms,
                depth=session.depth)
        return "committed", True

    return f"unknown tool {name}", False


def run_task(client, cur, task, mode, tw, *, max_steps=MAX_STEPS, model="claude-opus-5"):
    """Returns the exit path as a string. Scoring happens in the caller."""
    session = Session(cur, mode)
    messages = [{"role": "user", "content": task["description"] + "\n\n"
                 + task["add_description"]}]
    tools, empty_turns = tools_for(mode), 0

    for _ in range(max_steps):
        t0 = time.perf_counter()
        resp = client.messages.create(
            model=model, max_tokens=4096, system=system_for(mode),
            tools=tools,
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=messages,
        )
        llm_ms = (time.perf_counter() - t0) * 1000

        if resp.stop_reason in ("max_tokens", "refusal"):
            tw.step("execute_sql", response=resp, llm_ms=llm_ms, depth=session.depth)
            return resp.stop_reason                       # harness artifact

        calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not calls:
            empty_turns += 1
            if empty_turns > 1:
                return "end_turn"                         # never spin
            messages += [{"role": "assistant", "content": resp.content},
                         {"role": "user", "content":
                          "Continue by calling a tool, or commit_final_answer if done."}]
            continue

        call = calls[0]                                   # parallel use is disabled
        result, done = dispatch(session, call.name, call.input, tw,
                                llm_ms=llm_ms, response=resp)
        messages += [{"role": "assistant", "content": resp.content},
                     {"role": "user", "content": [{"type": "tool_result",
                                                   "tool_use_id": call.id,
                                                   "content": str(result)}]}]
        if done:
            session.finish()
            return "commit_final_answer"

    # Budget exhausted. COMMIT rather than roll back: Mode A's partial work is
    # already committed, so discarding Mode B's would score the arms differently.
    session.finish()
    return "max_steps"


# --------------------------------------------------------------------------
# Dry run — a scripted fake model. No API key, no budget, every exit path.
# --------------------------------------------------------------------------

class _Blk:
    def __init__(self, name, inp):
        self.type, self.name, self.input, self.id = "tool_use", name, inp, "toolu_x"


class _Resp:
    def __init__(self, stop_reason, blocks=()):
        self.stop_reason, self.content = stop_reason, list(blocks)
        self.usage = {"input_tokens": 3000, "output_tokens": 60}


class FakeClient:
    """Replays a scripted list of responses. `messages` mirrors the real client."""
    def __init__(self, script):
        self.script, self.i = script, 0
        self.messages = self

    def create(self, **_):
        r = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return r


class FakeCursor:
    def __init__(self, fail_on=None):
        self.description, self.rowcount, self.log, self.fail_on = None, 1, [], fail_on

    def execute(self, sql, *a):
        self.log.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("simulated driver error")

    def fetchall(self):
        return []


SCENARIOS = {
    "normal commit": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='1'"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", None),
    "explore then commit": ([
        _Resp("tool_use", [_Blk("checkpoint", {})]),
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='wrong'"})]),
        _Resp("tool_use", [_Blk("restore", {})]),
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='right'"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", None),
    "guard rejects DDL": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "CREATE INDEX i ON t (a(8))"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", None),
    "truncated": ([_Resp("max_tokens")], "B", None),
    "refused": ([_Resp("refusal")], "B", None),
    "end_turn no tool": ([_Resp("end_turn"), _Resp("end_turn")], "A", None),
    "driver error": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE boom SET a='1'"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", "boom"),
    "budget exhausted": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "SELECT * FROM t"})]),
    ], "B", None),
}


def _dry_run(run_dir="/tmp/dbagent-loop-demo"):
    task = {"description": "Set Wins to 12 for the Rams.",
            "add_description": "Table `Statistics`, headers Team,Year,Wins."}
    print("DRY RUN — scripted model, no API calls.\n")
    print(f"{'scenario':<22}{'mode':<6}{'exit path':<22}{'scored?':<9}{'steps':>6}  txn statements")
    print("-" * 108)
    for name, (script, mode, fail_on) in SCENARIOS.items():
        cur = FakeCursor(fail_on)
        tw = tracing.TraceWriter(run_dir, name.replace(" ", "_"), mode,
                                 system=system_for(mode), tools=tools_for(mode),
                                 model="fake", effort="high", thinking="adaptive",
                                 disable_parallel_tool_use=True, max_steps=6)
        exit_path = run_task(FakeClient(script), cur, task, mode, tw,
                             max_steps=6, model="fake")
        scored = exit_path in ("commit_final_answer", "max_steps")
        tw.result(passed=None, hash_got=None, hash_want=None,
                  error=None if scored else exit_path)
        txn = [s for s in cur.log if s.split()[0].upper()
               in ("START", "SAVEPOINT", "ROLLBACK", "COMMIT")]
        print(f"{name:<22}{mode:<6}{exit_path:<22}{str(scored):<9}{tw.n:>6}  {txn}")


if __name__ == "__main__":
    _dry_run()
