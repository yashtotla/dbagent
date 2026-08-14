# dbagent

Starter task for Prof. Kexin Rong's group (Georgia Tech). Option 3 of "Starter Tasks":
**Database Agent with Exploration.**

## What this is

Build an agent that runs DBBench modification tasks against MySQL in two modes, and
compare them.

- **Mode A — no exploration.** Every SQL statement commits. A wrong modification cannot
  be undone.
- **Mode B — checkpointed exploration.** Before a potentially state-changing action the
  agent may checkpoint the database, try the action, inspect the result, and either
  continue or restore and try an alternative.

Deliverable is a 1–2 page write-up plus optional code:

1. How checkpointing and restore were implemented — what state is saved, when a restore
   is triggered, what the overhead is.
2. A comparison of the two modes, analyzing cases where checkpointing enables recovery or
   exploration that linear execution cannot.
3. What I would do differently with more time.

Reference paper: *Toward Systems Foundations for Agentic Exploration*, arXiv 2510.05556.
It names three restoration primitives — replay-to-node, snapshot/restore, and
backtracking via compensating operations — and argues all three are too slow for
fine-grained agent exploration, calling for a "native fork" primitive instead. Its open
questions are (1) what other observers see during speculative branches, (2) external
side-effects that aren't fork-aware, (3) sub-millisecond native forking in databases and
runtimes.

The grading signal is explicitly *approach*, not polish. From the email: "The goal is not
necessarily to build a polished system, but to give you a chance to explore the problem
and give me a sense of how you approach an open-ended research and systems problem."

## Environment

- MySQL 8 in Docker: `docker run -d --name dbbench-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=pw mysql:8`
  The `mysql:8` tag currently resolves to **8.4.11**, not 8.0. Pin the version in the
  write-up's methods; defaults confirmed: `transaction_isolation=REPEATABLE-READ`, `autocommit=1`.
- Python via uv. Deps: `pymysql`, `anthropic`.
- `ANTHROPIC_API_KEY` in the environment.
- No Postgres, no Redis, no ORM. Raw SQL only.

## The data — verified facts

`data/dev.jsonl` is DBBench's dev split, copied from THUDM/AgentBench. 60 tasks:

- **40 modification tasks** — 20 `INSERT`, 20 `UPDATE`. These are the ones in scope.
  DBBench's modification family is `INSERT`/`UPDATE`/**`DELETE`** — AgentBench's `task.py`
  branches on that literal tuple in two places — but this split contains **zero** DELETE
  tasks. Scope sentence: "the dev split has no DELETE tasks", not "DBBench modifications
  are INSERT and UPDATE".
- 20 SELECT-family tasks (counting, ranking, comparison, aggregation-*, other). Out of scope.

Per-task fields that matter:

| field | notes |
|---|---|
| `type` | list of one string, e.g. `["INSERT"]` |
| `description` | the natural-language question given to the agent |
| `add_description` | table name + column names, also given to the agent |
| `table` | schema and rows, inlined. Single table for all 40 modification tasks |
| `label` | **gold SQL** for modification tasks (a list with one statement) |
| `answer_md5` | ground-truth hash of the final table state |
| `sql` | present ONLY on the 20 SELECT tasks. Not available on modification tasks |

Gotchas that cost real time if unknown:

1. **Gold SQL for modification tasks lives in `label`, not `sql`.** `sql` is absent on all
   40 of them.
2. **`answer_md5` is a string of a Python repr**, e.g. `"[('09aa8fbf72f39362970f95a1276b957c',)]"`.
   AgentBench produces it via `str(cursor.fetchall())`. Compare strings; do not parse it.
   **The trap is subtler than that:** `pymysql` returns a **tuple** where AgentBench's driver
   returned a **list**, so `str(cur.fetchall())` gives `(('09aa…',),)` against an expected
   `[('09aa…',)]` — the MD5 is byte-identical and every task fails anyway. Use
   `str(list(cur.fetchall()))`. This costs a full debugging cycle if you meet it after
   building the agent, because 0/40 reads as "the model is bad at this".
3. **Table and column names contain spaces** (`School Location Table`, `Date moved`).
   Backtick every identifier. All columns are created as `TEXT`.
4. `group_concat` truncates at `group_concat_max_len` (default 1024 bytes). **Confirmed both
   ways:** forcing it to 64 returns a *wrong hash with no error or warning*, so the bug is
   real and silent; but default (1024) and 1 MB both give 40/40. Tables are 12–44 rows and
   truncation starts around 170, so it is latent here, not binding. Worth one sentence in
   the write-up — it shows the scorer was checked rather than assumed.

## Scorer contract

Per task: create a fresh database, create the single table as all-`TEXT`, insert its rows,
let the agent act, then hash and compare.

```sql
SELECT md5(group_concat(rowhash ORDER BY rowhash)) AS hash
FROM (
  SELECT substring(MD5(CONCAT_WS(',', `col1`, `col2`, ...)), 1, 5) AS rowhash
  FROM `table name`
) AS sub;
```

Row-order-insensitive. Compare `str(cursor.fetchall())` against `answer_md5` exactly.

**Milestone 0, before anything else:** run each task's gold `label` SQL against a fresh
table and confirm the hash equals `answer_md5` for all 40. If this is not 40/40, every
downstream number is meaningless.

## Agent design

A while loop, not a model. No training.

```
messages = [system_prompt, question]
for step in range(max_steps):
    reply = llm(messages, tools=[...])
    dispatch the tool call, append the result
    stop on commit_final_answer
score = hash(final table) == answer_md5
```

Tools in Mode A: `execute_sql`, `commit_final_answer`.
Mode B adds whatever checkpoint/restore surface is chosen.

Reference behaviour worth knowing: AgentBench's own `MySQLDatabase.execute` calls
`conn.commit()` after **every** statement. That autocommit-per-statement choice is what
makes modifications irreversible — the irreversibility is a harness decision, not a MySQL
constraint.

## Checkpoint mechanisms — options, none chosen yet

The task doc allows any mechanism. Candidates, roughly in increasing cost:

All four were measured on MySQL 8.4.11, `game_results` (44 rows × 5 cols), localhost Docker.
Round-trip floor is 0.117 ms — measure it with `DO 1`, not `SELECT 1`, which returns a result
set and inflates the floor by ~16%.

- **`SAVEPOINT` / `ROLLBACK TO SAVEPOINT`** — InnoDB-native, MVCC-backed, no bulk copy.
  **Measured: creating a savepoint is below measurement resolution (it costs a round trip and
  nothing more); rollback is 0.209 ms with 1 row dirty, 0.646 ms with all 44.** Cost tracks
  rows dirtied, not table size. Limits all confirmed: DDL causes an implicit commit and
  destroys all savepoints — *silently*, surfacing only as error 1305 at the rollback, by
  which point the write is durable; savepoints are session-scoped so a reconnect loses them;
  uncommitted branch state is invisible to any other connection.
- **Replay-prefix** — reset to the init SQL and replay the accepted statements. Zero storage.
  **Measured: ≈6.4 ms + 0.15 ms × k.** The fixed reset dominates until k≈42, so at realistic
  path lengths it is effectively *constant*, not "linear in path length".
- **`mysqldump` / reload** — logical snapshot. **Measured: 105 ms**, almost entirely process
  spawn at this data size.
- **`docker commit`** — container snapshot. **Measured: 510 ms (n=3)**, at the bottom of the
  0.416–6.915 s Docker range the reference paper reports. Independent confirmation of their
  number is worth a sentence.

Open design question, deliberately unresolved: whether the spine of the write-up is the
straight two-mode comparison the doc asks for, or a sharper argument about
engine-native forking versus the generic mechanisms the reference paper benchmarks.
Do not resolve this unilaterally.

## Experiment hygiene

Whatever is compared, hold everything else fixed: same pinned model id, same prompts, same
task order, same max_steps. **Not temperature** — `temperature`, `top_p` and `top_k` are no
longer accepted on current Claude models and return a 400, so it cannot be held fixed
because it cannot be set. The equivalents are `output_config={"effort": ...}` and the
`thinking` setting; hold those fixed instead, and log them per run so "we held them fixed"
is provable rather than asserted. Only the checkpoint mechanism varies. (The
ActionEngine paper's Table 1 compares its own system on Claude 4.5 against a baseline on
GPT-4-Turbo — that confound is exactly what to avoid reproducing here.)

Log every `(step, sql, response, latency)` to `runs/<task_id>.jsonl`. Failure analysis
comes from reading traces, not from terminal output. Aggregate numbers alone will not
answer "cases in which checkpointing enables recovery that linear execution cannot" —
that requires naming specific tasks.

Report what the experiment cannot conclude: 40 tasks, one model, one benchmark, one
schema shape.

## Working agreement

- Yash writes the write-up. Every word of it. Claude does not draft prose for it and does
  not produce outline bullets that become its skeleton — the reviewer is the paper's
  author and the point is that the thinking is his.
- Claude is a full collaborator on the code.
- Scope discipline: this is a weekend project. Build the smallest thing that produces an
  honest number, then analyze it. Resist adding mechanisms, benchmarks, or abstractions
  that are not required by a question being asked.
- Do not use AgentBench's own harness (AgentRL server/client + docker-compose). Borrow its
  `dev.jsonl` and reimplement the ~60 lines of init-SQL and hashing. Full control over
  transaction boundaries is required, since that is the variable under study.
- Prefer short, direct explanations. Examples and parallels over jargon.
