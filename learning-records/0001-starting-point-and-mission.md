# Starting point: mission established, transaction level calibrated

Mission established as two-part — land the Georgia Tech starter task *and* build the underlying
skill of doing open-ended research well (both selected explicitly over the narrower framings of
"learn agentic systems" or "fix DB fundamentals"). All four gap areas named as live: MySQL
transaction internals, agentic exploration as a field, experiment design, and agent-loop
engineering. See [[MISSION.md]].

**Prior knowledge disclosed:** comfortable with `BEGIN`/`COMMIT`/`ROLLBACK`; savepoints,
isolation levels, and implicit-commit rules self-reported as fuzzy. This sets the floor —
teach savepoint and MVCC semantics from scratch, but do not re-explain what a transaction is.

**Implications for sequencing.** Because the mission's second half is research skill rather than
knowledge alone, lessons should carry their methodology in the open: cite primary sources
inline, flag unverified claims as unverified, and make the user reproduce results rather than
accept them. Lesson 01 does this deliberately — it teaches savepoint semantics *and* models
verification by reproducing a failure locally, and it hands back an unverified premise from
`CLAUDE.md` (AgentBench's per-statement `conn.commit()`) as the user's own action item rather
than asserting it.

**Repo state at session start:** spec-complete, code-empty. `CLAUDE.md` is 162 lines of design
doc; `src/dbagent/__init__.py` is a hello-world stub; `runs/` is empty; Milestone 0 not started;
no MySQL container running. Every dataset claim in `CLAUDE.md` was independently verified
against `data/dev.jsonl` and holds.
