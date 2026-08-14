# Agentic Exploration & Database Checkpointing — Resources

Curated, verified, and annotated. Every claim in a lesson traces back to something here.
If a source turned out to be shallow or wrong, it gets deleted rather than demoted.

## Knowledge

### The reference paper

- [Paper: "Toward Systems Foundations for Agentic Exploration" — Xu, Zhou, Wu & Kaffes (arXiv:2510.05556, 7 Oct 2025)](https://arxiv.org/abs/2510.05556)
  Four-page workshop-style position paper. Names three restoration primitives (replay-to-node,
  snapshot/restore, backtracking via compensating operations), benchmarks six generic
  snapshot/restore mechanisms, and argues all are too slow — calling for a native fork
  primitive. Use for: the framing of the whole project, and the three open challenges.
  **The HTML version renders fully — [arxiv.org/html/2510.05556v1](https://arxiv.org/html/2510.05556v1)
  — read that rather than the PDF, whose text extracts poorly.**

  Measured restore latencies worth citing rather than re-deriving:
  CRIU 0.060–1.445 s · Docker 0.416–6.915 s · checkpoint-lite 0.418–4.622 s ·
  Podman 0.835–12.914 s · Podman+CRIU 1.657–26.648 s · AWS VM ≈353 s.

### MySQL primary documentation

- [MySQL 8.0 Reference Manual §15.3.4 — SAVEPOINT, ROLLBACK TO SAVEPOINT, RELEASE SAVEPOINT](https://dev.mysql.com/doc/refman/8.0/en/savepoint.html)
  The complete savepoint contract in about four normative sentences. Use for: what a savepoint
  guarantees, name-reuse semantics, and the fact that row locks survive a partial rollback.

- [MySQL 8.0 Reference Manual §15.3.3 — Statements That Cause an Implicit Commit](https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html)
  The exhaustive DDL list. Use for: predicting which agent-issued statements silently destroy a
  checkpoint. The single highest-value page for Mode B correctness.

- [MySQL 8.0 Reference Manual §17.3 — InnoDB Multi-Versioning](https://dev.mysql.com/doc/refman/8.0/en/innodb-multi-versioning.html)
  `DB_TRX_ID`, `DB_ROLL_PTR`, undo logs, consistent reads. Use for: explaining *why* rollback is
  cheap and *what* a second connection observes mid-branch — i.e. the mechanism behind the
  paper's "fork semantics" challenge.

### Benchmark source

- [THUDM/AgentBench](https://github.com/THUDM/AgentBench) — DBBench lives at
  `src/server/tasks/dbbench/` (`__init__.py` re-exports from `task.py`).
  **Verified:** `_build_init_sql()` creates every column as `TEXT` with backticked identifiers
  via `CREATE TABLE IF NOT EXISTS`; scoring goes through `DBResultProcessor.calculate_tables_hash_async`
  → `compare_results`.
  **Not yet verified:** the per-statement `conn.commit()` claim. It lives in the `interaction`
  module. Clone and read it — it is the premise of the project.

## Wisdom (Communities)

Not yet discussed with Yash — proposed, not adopted:

- **Prof. Rong's group itself.** The highest-signal community available here, and the actual
  audience. Questions asked of the reviewer before submitting are usually worth more than any
  forum answer.
- [r/databasedevelopment](https://reddit.com/r/databasedevelopment) — practitioners who build
  storage engines rather than use them. Use for: sanity-checking a claim about InnoDB internals
  before it goes in the write-up.
- [DB Weekly](https://dbweekly.com/) / [The Morning Paper archives](https://blog.acolyer.org/) —
  for calibrating what a good short systems write-up reads like.

## Gaps

- **No source yet for how to write a 1–2 page systems research note.** Worth finding one strong
  exemplar — a HotOS-style position paper with a tight evaluation section — as a structural
  model. (Structure only. Yash writes the prose.)
- **No independent measurement of `SAVEPOINT` restore latency** at DBBench table sizes. Nobody
  publishes this because it is too small to be interesting generally — but it is precisely the
  number this project needs. Must be measured, not cited.
- **No source on agent-side exploration policy** — *when* an agent should decide to branch.
  The paper covers mechanism, not policy. This may be where the project's original contribution
  actually lives.
