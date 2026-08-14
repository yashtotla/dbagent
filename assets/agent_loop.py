"""The agent loop. Three outcomes, no recovery.

Teaching-workspace asset for lesson 06 (rewritten after review). Dry run:

    uv run python assets/agent_loop.py

THREE OUTCOMES
--------------
    1. completed   agent called commit_final_answer -> hash the table, compare
    2. exception   anything unexpected -> RAISE. Stop the process and debug.
    3. budget      max_steps without committing -> RAISE. Stop and debug.

There is no fourth bucket, no "excluded as harness artifact", no partial credit.
During development every non-happy path is a bug you can still fix, and a harness
that absorbs bugs into a results column hides exactly what you need to see.

Graceful degradation is for an unattended production run. This is 40 tasks with
you watching. Crash, read the stack trace, fix, re-run.

STRICT MODE
-----------
`strict=True` (the default) also raises when the agent's own SQL errors. Start
here: if the agent is writing broken SQL, the prompt or the tool description is
wrong and you want to know immediately. Once the run is clean, flip to
`strict=False` and bad SQL becomes an ordinary tool result the agent can react
to -- which is the real tool contract, and normal agent behaviour rather than a
harness failure.

WHAT SCORING ACTUALLY IS
------------------------
The scorer hashes a table. It does not know an agent exists, whether it finished,
or how many turns it took. So there is no "how do we score an incomplete task"
rule to design -- there is only "what is on the table when we hash it," and on
outcomes 2 and 3 you never get there because you stopped to look.
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


def _tool(name, description, props=None):
    return {"name": name, "description": description, "strict": True,
            "input_schema": {"type": "object", "additionalProperties": False,
                             "properties": props or {},
                             "required": list((props or {}).keys())}}


EXECUTE_SQL = _tool(
    "execute_sql",
    "Run one SQL statement against the task's table and return its result. "
    "Call this to inspect state or to make a modification.",
    {"sql": {"type": "string", "description": "A single SQL statement."}})
COMMIT_FINAL = _tool(
    "commit_final_answer",
    "Call when the table is in its final state and the task is complete.")
CHECKPOINT = _tool(
    "checkpoint", "Record the current table state so you can return to it later.")
RESTORE = _tool(
    "restore", "Undo everything since the most recent checkpoint.")


def tools_for(mode):
    # Mode B carries two extra tools and a longer system prompt. That confound is
    # unavoidable by construction -- state it, measure the policy change, do not
    # try to net it out (Reference 02).
    return [EXECUTE_SQL, COMMIT_FINAL] + ([CHECKPOINT, RESTORE] if mode == "B" else [])


def system_for(mode):
    return SYSTEM + (SYSTEM_B_EXTRA if mode == "B" else "")


class HarnessError(RuntimeError):
    """Something the harness did not expect. Always a bug to fix, never a result."""


class BudgetExhausted(RuntimeError):
    """max_steps without commit_final_answer. Look at the trace before changing anything."""


class Session:
    """Owns the transaction and the savepoint stack. The agent never writes
    transaction SQL -- it calls tools and the harness issues the statements."""

    def __init__(self, cur, mode):
        self.cur, self.mode, self.depth = cur, mode, 0
        if mode == "B":
            cur.execute("START TRANSACTION")
            cur.execute("SAVEPOINT sp_0")          # the restore floor

    def checkpoint(self):
        self.depth += 1
        self.cur.execute(f"SAVEPOINT sp_{self.depth}")
        return f"checkpoint recorded (depth {self.depth})"

    def restore(self):
        # Roll back to the most recent checkpoint and KEEP it, so trying a second
        # alternative at the same decision point costs one call.
        self.cur.execute(f"ROLLBACK TO SAVEPOINT sp_{self.depth}")
        return f"restored to checkpoint (depth {self.depth})"

    def commit(self):
        if self.mode == "B":
            self.cur.execute("COMMIT")


def dispatch(session, name, args, tw, *, llm_ms, response, strict):
    """Run one tool call. Returns (result_for_agent, done). Writes one trace step."""
    cur, t0 = session.cur, time.perf_counter()

    if name == "execute_sql":
        sql = args["sql"]
        reason = sql_guard.check(sql)                       # the enforcement point
        if reason:
            tw.step("rejected", response=response, llm_ms=llm_ms,
                    depth=session.depth, sql=sql, reason=reason)
            return reason, False
        try:
            cur.execute(sql)
            rows = cur.fetchall() if cur.description else []
        except Exception as e:
            tw.step("execute_sql", response=response, llm_ms=llm_ms,
                    db_ms=(time.perf_counter() - t0) * 1000, depth=session.depth,
                    sql=sql, rowcount=None, db_error=f"{type(e).__name__}: {e}")
            if strict:
                raise HarnessError(f"agent SQL failed: {sql!r} -> {e}") from e
            return f"error: {e}", False
        tw.step("execute_sql", response=response, llm_ms=llm_ms,
                db_ms=(time.perf_counter() - t0) * 1000, depth=session.depth,
                sql=sql, rowcount=cur.rowcount, db_error=None)
        return f"{cur.rowcount} row(s) affected. {rows[:20]}", False

    if name in ("checkpoint", "restore"):
        out = getattr(session, name)()
        tw.step(name, response=response, llm_ms=llm_ms,
                db_ms=(time.perf_counter() - t0) * 1000, depth=session.depth)
        return out, False

    if name == "commit_final_answer":
        tw.step("commit_final_answer", response=response, llm_ms=llm_ms,
                depth=session.depth)
        return "committed", True

    raise HarnessError(f"model called an unknown tool: {name!r}")


def run_task(client, cur, task, mode, tw, *, max_steps=MAX_STEPS,
             model="claude-opus-5", strict=True):
    """Outcome 1 returns None. Outcomes 2 and 3 raise. Nothing else happens."""
    session = Session(cur, mode)
    messages = [{"role": "user",
                 "content": f"{task['description']}\n\n{task['add_description']}"}]

    for step in range(1, max_steps + 1):
        t0 = time.perf_counter()
        resp = client.messages.create(
            model=model, max_tokens=8192, system=system_for(mode),
            tools=tools_for(mode),
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=messages,
        )
        llm_ms = (time.perf_counter() - t0) * 1000

        # Anything other than a tool call is a bug in the prompt, the budget or
        # the tool schema. Stop and look at it.
        if resp.stop_reason != "tool_use":
            tw.step("halt", response=resp, llm_ms=llm_ms, depth=session.depth)
            raise HarnessError(
                f"step {step}: stop_reason={resp.stop_reason!r}, expected 'tool_use'")

        calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if len(calls) != 1:                     # parallel tool use is disabled
            raise HarnessError(f"step {step}: got {len(calls)} tool calls, expected 1")

        call = calls[0]
        result, done = dispatch(session, call.name, call.input, tw,
                                llm_ms=llm_ms, response=resp, strict=strict)
        messages += [
            {"role": "assistant", "content": resp.content},
            {"role": "user", "content": [{"type": "tool_result",
                                          "tool_use_id": call.id,
                                          "content": str(result)}]},
        ]
        if done:
            session.commit()
            return

    raise BudgetExhausted(
        f"{max_steps} steps without commit_final_answer — read "
        f"{tw.path} before changing max_steps")


# --------------------------------------------------------------------------
# Dry run — scripted model, no API key, no budget.
# --------------------------------------------------------------------------

class _Blk:
    def __init__(self, name, inp):
        self.type, self.name, self.input, self.id = "tool_use", name, inp, "toolu_x"


class _Resp:
    def __init__(self, stop_reason, blocks=()):
        self.stop_reason, self.content = stop_reason, list(blocks)
        self.usage = {"input_tokens": 3000, "output_tokens": 60}


class FakeClient:
    def __init__(self, script):
        self.script, self.i, self.messages = script, 0, self

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
    "1 happy path": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='1'"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", None),
    "1 happy, explored": ([
        _Resp("tool_use", [_Blk("checkpoint", {})]),
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='wrong'"})]),
        _Resp("tool_use", [_Blk("restore", {})]),
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='right'"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", None),
    "1 happy, guard fired": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "CREATE INDEX i ON t (a(8))"})]),
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE t SET a='1'"})]),
        _Resp("tool_use", [_Blk("commit_final_answer", {})]),
    ], "B", None),
    "2 exception: truncated": ([_Resp("max_tokens")], "B", None),
    "2 exception: no tool call": ([_Resp("end_turn")], "A", None),
    "2 exception: bad SQL": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "UPDATE boom SET a='1'"})]),
    ], "B", "boom"),
    "3 budget exhausted": ([
        _Resp("tool_use", [_Blk("execute_sql", {"sql": "SELECT * FROM t"})]),
    ], "B", None),
}


def _dry_run(run_dir="/tmp/dbagent-loop-demo"):
    task = {"description": "Set Wins to 12 for the Rams.",
            "add_description": "Table `Statistics`, headers Team,Year,Wins."}
    print("DRY RUN — scripted model, no API calls.\n")
    print(f"{'scenario':<26}{'mode':<6}{'outcome':<16}{'what you do':<24}{'steps':>6}")
    print("-" * 104)
    for name, (script, mode, fail_on) in SCENARIOS.items():
        cur = FakeCursor(fail_on)
        tw = tracing.TraceWriter(run_dir, name.replace(" ", "_").replace(":", ""), mode,
                                 system=system_for(mode), tools=tools_for(mode),
                                 model="fake", effort="high", thinking="adaptive",
                                 disable_parallel_tool_use=True, max_steps=6)
        try:
            run_task(FakeClient(script), cur, task, mode, tw, max_steps=6, model="fake")
            outcome, action = "completed", "hash and compare"
        except BudgetExhausted:
            outcome, action = "budget", "STOP — read the trace"
        except HarnessError:
            outcome, action = "exception", "STOP — read the trace"
        tw.result(passed=None, hash_got=None, hash_want=None, error=outcome)
        print(f"{name:<26}{mode:<6}{outcome:<16}{action:<24}{tw.n:>6}")

    print("\nThree outcomes. Two of them stop the process — no excluded bucket,")
    print("no partial credit, nothing silently absorbed into the results.")


if __name__ == "__main__":
    _dry_run()
