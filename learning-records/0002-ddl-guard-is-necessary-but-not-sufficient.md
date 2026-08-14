# Lesson 01 understood; "block DDL" identified as necessary but not sufficient

After Lesson 01 Yash stated the takeaway as: *"we want to make sure that we don't allow the
agent to run any autocommit ddl to verify the checkpoint and restore mechanism."* The core is
correct and was reached independently — agent-issued DDL silently commits the branch and
destroys the savepoint, so the tool boundary must guard against it. That is the load-bearing
insight of the lesson.

Two edges needed correcting, both verified empirically on MySQL 8.4.11 rather than asserted:

1. **`autocommit` and *implicit commit* are separate mechanisms.** Setting `autocommit = 0`
   inside an explicit `START TRANSACTION` does **not** protect the savepoint — DDL still fired
   the implicit commit and `ROLLBACK TO SAVEPOINT` still raised error 1305. The phrase
   "autocommit DDL" fuses two independent things and would read as an error in the write-up.

2. **DDL is one of four savepoint killers, and the only one that is DDL.** Confirmed live: a
   bare `COMMIT` kills the savepoint with no DDL present; a bare `BEGIN` kills it too (it
   implicitly commits first); and a `pymysql` reconnect destroys the whole transaction. The
   correct guard is therefore not "no DDL" but **"the agent may not mutate transaction state"** —
   DDL *plus* transaction-control statements *plus* a held-open single connection per task.

**Implication that shifts the experiment design.** Restricting the agent's action space in
Mode B but not Mode A introduces a second variable, which violates the experiment-hygiene rule
in `CLAUDE.md` ("hold everything else fixed; only the checkpoint mechanism varies"). The
restriction must be applied to **both** modes. This is verified to be free: **0 of the 40 gold
`label` statements contain any DDL or transaction-control keyword**, and all 40 are single
statements — so the guard is non-binding on the gold path and costs no reachable score in
either mode. Records what the guard rejects; a rejected statement is a data point about the
agent, not a harness failure.

Next session should build on this rather than re-teach it. See [[MISSION.md]] and
[[0001-starting-point-and-mission]].
