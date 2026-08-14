"""The statement guard for the execute_sql tool.

Teaching-workspace asset for lesson 04. Run the self-test:

    uv run python assets/sql_guard.py

The agent can only reach the database through tools the harness dispatches. That
dispatcher is the only enforcement point that exists -- the system prompt is
documentation, and documentation does not stop bad input.

WHY AN ALLOWLIST AND NOT A BLOCKLIST
------------------------------------
A blocklist requires you to enumerate every dangerous statement. Miss one and it
fails OPEN. Concretely, `/* harmless */ DROP TABLE t` extracts no leading keyword
at all -- a blocklist finds nothing forbidden and executes the DROP, which MySQL
happily runs.

An allowlist requires you to enumerate only what the task NEEDS. The same input
extracts no keyword, the empty string is not in ALLOWED, and it fails CLOSED.

Verified: all 40 gold `label` statements are INSERT (20) or UPDATE (20), so the
allowlist below is non-binding on every reachable correct answer.
"""
import json
import re

# Strip comments before looking for the leading keyword. Without this,
# "/* x */ DROP TABLE t" yields no keyword and slips past a blocklist.
_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*|#[^\n]*", re.S)
_LEADING = re.compile(r"\s*([A-Za-z_]+)")

# What the agent is permitted to send.
#
# INSERT / UPDATE / DELETE are DBBench's three modification types -- verified in
# AgentBench's task.py, which branches on the literal tuple ("INSERT", "DELETE",
# "UPDATE") in two places. The dev split happens to contain only INSERT (20) and
# UPDATE (20) and zero DELETE, but that is a property of this split, not of the
# benchmark. DELETE belongs here on the same footing as the other two.
#
# Reads are included so the agent can inspect state mid-branch, which is the
# whole point of exploration.
ALLOWED = frozenset({
    "SELECT", "INSERT", "UPDATE", "DELETE",
    "SHOW", "DESCRIBE", "DESC", "EXPLAIN",
})

# NOT here, and deliberately: SAVEPOINT, ROLLBACK, COMMIT, BEGIN, START.
# The agent still needs those capabilities in Mode B -- it reaches them through
# dedicated checkpoint() / restore() / commit_final_answer() tools instead of
# through raw SQL. Routing them through typed tools rather than an opaque string
# lets the harness own savepoint naming (reusing a name REPLACES rather than
# nests), emit one countable branch event per checkpoint, and validate a restore
# handle before issuing it. See reference/tool-boundary.html.


def leading_keyword(sql: str) -> str:
    """The statement's verb, with comments stripped. '' if there isn't one."""
    m = _LEADING.match(_COMMENT.sub(" ", sql))
    return m.group(1).upper() if m else ""


def check(sql: str) -> str | None:
    """None if the statement may run; otherwise a reason string for the agent.

    The reason goes back to the agent as a tool result so it can try something
    else, and into the trace so a rejection is visible as agent behaviour rather
    than disappearing as a harness detail.
    """
    kw = leading_keyword(sql)
    if not kw:
        return "rejected: no recognisable SQL statement"
    if kw not in ALLOWED:
        return (f"rejected: {kw} is not permitted. "
                f"Allowed statements: {', '.join(sorted(ALLOWED))}")
    return None


# --------------------------------------------------------------------------
# Self-test. Every case below was verified against MySQL 8.4.11.
# --------------------------------------------------------------------------
CASES = [
    # (sql, should_be_allowed, why this case exists)
    ("UPDATE `t` SET `a` = '1'", True, "the ordinary case"),
    ("INSERT INTO `t` (`a`) VALUES ('x')", True, "the other ordinary case"),
    ("SELECT * FROM `t`", True, "agent inspecting state mid-branch"),
    ("INSERT INTO t (a) VALUES ('DROP TABLE customers')", True,
     "DDL inside a string literal -- a substring blocklist wrongly rejects this"),
    ("  update t set a='1'  ", True, "lowercase and padded"),

    ("CREATE INDEX idx ON t (a(10))", False, "DDL: implicit commit kills the savepoint"),
    ("ALTER TABLE t ADD COLUMN b TEXT", False, "DDL"),
    ("DROP TABLE t", False, "DDL"),
    ("TRUNCATE TABLE t", False, "DDL"),
    ("/* harmless */ DROP TABLE t", False,
     "comment-prefixed DDL: defeats a blocklist, fails closed against an allowlist"),
    ("COMMIT", False, "routed to commit_final_answer(), not withheld"),
    ("ROLLBACK", False, "bare rollback discards the whole task; restore(0) is the tool"),
    ("BEGIN", False, "implicitly commits first"),
    ("START TRANSACTION", False, "implicitly commits first"),
    ("SET autocommit = 1", False, "implicitly commits"),
    ("SAVEPOINT sp_evil", False, "routed to checkpoint(); the harness owns naming"),
    ("LOCK TABLES t WRITE", False, "implicitly commits"),
    ("USE otherdb", False, "switching schema mid-task"),
    ("", False, "empty input"),
    ("-- just a comment", False, "no statement at all"),
]


def main():
    failures = 0
    for sql, should_allow, why in CASES:
        allowed = check(sql) is None
        ok = allowed == should_allow
        failures += not ok
        mark = "ok  " if ok else "FAIL"
        verdict = "allow" if allowed else "reject"
        print(f"  {mark} {verdict:<6} {sql[:44]:<46} {why}")

    labels = [json.loads(l) for l in open("data/dev.jsonl")]
    gold = [r["label"][0] for r in labels if r["type"][0] in ("INSERT", "UPDATE")]
    blocked = [s for s in gold if check(s) is not None]
    print(f"\n  {len(CASES) - failures}/{len(CASES)} guard cases pass")
    print(f"  gold labels blocked: {len(blocked)}/{len(gold)} "
          f"(must be 0 -- the guard costs no reachable score)")
    return 1 if failures or blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
