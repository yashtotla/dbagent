# DELETE is a benchmark type, not a judgment call; rejected ≠ withheld

Two corrections from Yash on lesson 04, both from him reading the guard's contents rather than
its argument. He accepted the allowlist reasoning ("I agree that an allowlist is better for such a
small number of tasks") and then audited what was *in* it — the same move as
[[0003-placebo-control-refuted]].

**1. `DELETE` is one of DBBench's three modification types.** Lesson 04 framed it as a judgment
call I'd made ("so a branch can correct itself"), and invited him to argue against it. Wrong
framing. Verified in AgentBench's `task.py`, which branches on the literal tuple
`("INSERT", "DELETE", "UPDATE")` in two places. The dev split contains 20 `INSERT`, 20 `UPDATE`,
and **zero `DELETE`** — a property of *this split*, not of the benchmark.

The underlying error is worth naming because it recurs: I repeatedly wrote "all 40 gold labels are
INSERT (20) or UPDATE (20)", which is true, and then let that stand in for the benchmark's category
definition, which it isn't. **A split's contents are not a benchmark's schema.** This matters for
the write-up's scope sentence — "the dev split contains no DELETE tasks" is defensible, "DBBench
modifications are INSERT and UPDATE" is not, and a reviewer who knows the benchmark would catch it.

**2. "Doesn't the agent need SAVEPOINT / COMMIT / ROLLBACK?"** Yes — and the guard rejecting them
is not withholding the capability, it's routing it through `checkpoint()` / `restore(handle)` /
`commit_final_answer()`. This is the lesson's own bash-versus-dedicated-tool distinction applied one
level in, and the lesson failed to say so, which is why the question was reasonable. Owning the
statement buys three things the harness cannot get from an opaque string:

- **Savepoint naming** — a reused name *replaces* rather than nests, so an agent writing
  `SAVEPOINT sp1` twice silently loses its outer branch. Depth-indexed names must come from the
  harness.
- **Countable branches** — one structured trace event per checkpoint. [[0003-placebo-control-refuted]]
  settled that the replacement for the dead placebo is *measuring the policy change*; that requires
  branch structure to be legible, not parsed out of SQL strings.
- **Handle validation** — refuse `restore(3)` when depth 3 is gone, rather than surfacing error 1305
  mid-branch.

Bare `COMMIT` and bare `ROLLBACK` are genuinely never needed: commit happens once via
`commit_final_answer`, and "reset to start" is `restore(0)` against an `sp_0` taken immediately
after `START TRANSACTION`.

**Implication for teaching.** He now audits *contents* as reliably as he audits *arguments* — and
both corrections here were factual/structural rather than conceptual, which is a different and
harder class than [[0002-ddl-guard-is-necessary-but-not-sufficient]]. Two rules follow: never
present a benchmark-derived constant as a judgment call without checking the benchmark's own source
first, and when a guard rejects something the agent plausibly needs, say in the same breath where
the capability went. A rejection list without its routing table reads as a capability list.
