# dbagent

Starter task for Prof. Kexin Rong's group (Georgia Tech): **Database Agent with Exploration**.

An agent runs DBBench modification tasks against MySQL in two modes:

- **Mode A** — every statement commits. A wrong modification cannot be undone.
- **Mode B** — the agent may `checkpoint` before a risky write and `restore` to undo it.

Both modes share one model, one base prompt, one guard and one step budget. Mode B
adds two tools and the paragraph that describes them; nothing else differs.

## Setup

MySQL 8 in Docker:

```bash
docker run -d --name dbbench-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=pw mysql:8
```

Python via [uv](https://docs.astral.sh/uv/), and API keys:

```bash
uv sync
cp .env.example .env    # then fill in the keys for the providers you use
```

For the local model, install [Ollama](https://ollama.com) and pull Qwen. The default
4096-token context is too small for this loop, which resends the full history each turn:

```bash
ollama pull qwen2.5:7b
OLLAMA_CONTEXT_LENGTH=16384 ollama serve
```

## Running

```bash
uv run python -m src.main --mode A --model qwen2.5-7b --limit 40
uv run python -m src.main --mode B --model qwen2.5-7b --limit 40
```

| flag | meaning |
|---|---|
| `--mode` | `A` (no exploration) or `B` (checkpoint/restore) |
| `--model` | alias from `src/utils/constants.py` |
| `--limit` | number of tasks (default 3) |
| `--offset` | index of the first task (default 0; UPDATE tasks start at 20) |
| `--tasks` | explicit ids (`--tasks task_24 task_26`), overriding the two above |

Models live in `MODEL_REGISTRY`; adding one is a registry entry, not a code change.

| alias | model | endpoint |
|---|---|---|
| `qwen2.5-7b` | `qwen2.5:7b` | local Ollama |
| `qwen3.6-27b-groq` | `qwen/qwen3.6-27b` | Groq |
| `qwen3.6-27b-ali` | `qwen3.6-27b` | Alibaba Cloud Model Studio |

The provider is part of the alias because it changes behaviour, not just latency —
on Groq this model emits XML instead of JSON tool calls often enough to need
resampling, and on Alibaba it does not.

Runs are serial by design — savepoints are session-scoped. Two runs at once are safe
(`TASK_DB` is per-process) but each still needs its own MySQL connection.

## Results

All 40 modification tasks, one run per mode, scored by order-insensitive table hash.

| configuration | Mode A | Mode B | tasks run | |
|---|---|---|---|---|
| `qwen2.5-7b` (Ollama) | 22/40 | 21/40 | 36/40 | 11 protocol failures |
| `qwen3.6-27b-groq` | 10/20 | 1/20 | 16/20 | pilot; quota-damaged, Mode B unusable |
| `qwen3.6-27b-ali` | **32/40** | **31/40** | **40/40** | clean instrument, 0 protocol failures |

The Groq run covers only the 20 tasks the 7B failed and is not a paired comparison —
Mode A exhausted the rate limit and 19 of 20 Mode B tasks died on HTTP 429 before their
first call. It is reported because it exposed the tool-call bug below, not as a result.

Paired discordance never reached the ~6 clean flips that would be reportable. On the
7B, Mode B recovered `task_31` and lost `task_56` and `task_57`. On Alibaba, Mode B
recovered nothing and lost `task_47` to a provider content filter.

### Exploration was available and unused

| configuration | Mode B runs | checkpoints | restores |
|---|---|---|---|
| `qwen2.5-7b` | 40 | 4 | 0 |
| `qwen3.6-27b-groq` | 20 | 0 | 0 |
| `qwen3.6-27b-ali` | 40 | 1 | 0 |
| **total** | **100** | **5** | **0** |

Maximum savepoint depth observed was 1, so the decision to keep `restore()` flat never
bound. The one Alibaba checkpoint (`task_34`) preceded a `DELETE` of the whole table;
the agent then rebuilt all 16 rows by hand rather than calling `restore`.

### Restore cost

Measured with `assets/bench_restore.py`, MySQL 8.4.11 in Docker on localhost, on
`game_results` (44 rows, the largest of the 40 tables), warmed up, median of n, floor
measured with `DO 1`.

| mechanism | n | p50 | net of floor | × savepoint |
|---|---|---|---|---|
| `DO 1` — round-trip floor | 400 | 0.117 ms | — | — |
| `SAVEPOINT` | 400 | 0.104 ms | below resolution | — |
| `ROLLBACK TO SAVEPOINT`, 1 row dirty | 400 | 0.209 ms | 0.092 ms | 1× |
| `ROLLBACK TO SAVEPOINT`, 44 rows dirty | 400 | 0.646 ms | 0.529 ms | 3× |
| replay-prefix, k=0 | 40 | 6.37 ms | 6.25 ms | 30× |
| replay-prefix, k=20 | 40 | 9.37 ms | 9.25 ms | 45× |
| `mysqldump` + reload | 10 | 105 ms | 105 ms | 504× |
| `docker commit` | 3 | 510 ms | 510 ms | 2440× |

Rollback cost tracks rows dirtied, not table size — InnoDB unwinds the undo log.
Replay-prefix fits `≈ 6.4 ms + 0.15 ms × k`; the fixed reset dominates until k ≈ 42, so
at realistic path lengths it is effectively constant rather than linear in path length.

These are not like-for-like: the mechanisms restore different amounts of state.
`ROLLBACK TO SAVEPOINT` covers rows in one transaction and misses DDL, the filesystem
and process memory; `docker commit` covers the container filesystem. The comparison is
coverage against cost, not a speed ranking.

### Why the eight Alibaba Mode A failures failed

Every failure is an INSERT task, and the same eight fail in both modes. All 20 UPDATE
tasks pass in Mode A.

| class | n | tasks | |
|---|---|---|---|
| gold not derivable from the task | 3 | 25, 38, 39 | `task_38` needs `October = '9'`, a value absent from the description; `task_39` needs `'heath + grove'` where the description says `heath+grove` |
| agent corrected instead of appending | 2 | 28, 37 | gold is the plain INSERT; a near-duplicate row already existed and the agent tidied it |
| convention mismatch | 2 | 27, 34 | gold wants `'August 11 , 2021'` — space before the comma, as in all 23 existing rows |
| destroyed state, inexact rebuild | 1 | 34 (Mode A) | deleted the totals row, recomputed `137,220` in place of the unreadable `8,099` |

Gold rows were recovered by reimplementing the scorer's hash in Python and solving for
the missing row — for `task_25`, 10,192 candidate reconstructions were tested and none
matched. Three unwinnable tasks put the real ceiling at **37**, so Mode A's 32 is 86% of
what is achievable rather than 80% of nominal.

`task_33` is the counter-example to matching neighbouring rows: its gold `First Episode`
is `Rio`, unquoted, while every existing row quotes episode names (`"Blood Brothers"`).
The benchmark's gold answers are not internally consistent about formatting.

### Tool-call protocol, by provider

Both models fail to emit valid tool calls, in different dialects, and neither failure is
visible through the OpenAI-compatible response.

- **`qwen2.5:7b` on Ollama** escapes a SQL quote as `\'` inside the JSON arguments. That
  is not a legal JSON escape, so Ollama's parser discards the call and returns an empty
  message — 74 completion tokens spent, `content` empty, `tool_calls` null. Deterministic:
  identical on five consecutive calls. Visible only via `/api/generate` with `raw: true`.
- **`qwen3.6-27b` on Groq** emits `<function=execute_sql><parameter/sql>` XML instead of
  JSON on roughly 1 call in 8, which Groq rejects with HTTP 400 `tool_use_failed`. The
  same weights on Alibaba produced zero malformed calls in 80 tasks.

The loop resamples up to `MAX_RESAMPLES` on `tool_use_failed` and records each one as a
`malformed_tool_call` step, since how reliably a model holds the protocol is itself a
result. It does not retry on 429.

## Layout

```
src/
  main.py          argparse entry point
  experiment.py    runs N tasks in one mode, prints every step
  agent/
    loop.py        the agent loop and tool dispatch
    session.py     transaction and savepoint stack
    guard.py       SQL allowlist enforced at the tool boundary
    prompts.py     system prompts and tool schemas
  db/mysql.py      connection, per-task table setup, the scorer's hash
  utils/
    config.py      DSN, step budget, model resolution
    constants.py   MODEL_REGISTRY
    tasks.py       loading the DBBench dev split
    trace.py       writing and analysing run traces
data/dev.jsonl     DBBench dev split (60 tasks; 40 are modifications)
runs/              one JSONL trace per task per mode, grouped by model alias
```

## Design decisions

These shaped the harness and are the reason several results are interpretable.

- **`SAVEPOINT` / `ROLLBACK TO SAVEPOINT`**, not replay-prefix, `mysqldump` or
  `docker commit`. It is the engine-native primitive, and the alternatives cost two to
  three orders of magnitude more to restore state these tasks never touch.
- **Per-task DDL must finish before `START TRANSACTION`.** DDL causes an implicit
  commit, which silently destroys every savepoint in the session and surfaces much
  later as error 1305.
- **No connection pooling, no auto-reconnect.** Savepoints are session-scoped, so a
  reconnect mid-task destroys the branch without an error.
- **A step is one LLM call**, not one tool call. The agent may hit the database as
  often as it likes within a step; only model calls consume the budget.
- **Batched tool calls are executed in array order, not rejected.** Providers batch
  regardless of `parallel_tool_calls`, and Mode B batches more because it offers more
  tools — rejecting batches would have penalised Mode B for its tool count and read as
  "checkpointing hurts".
- **`restore()` is flat.** It returns to the most recent checkpoint and keeps it, so a
  second alternative at one decision point costs one call. Depth is logged to show
  whether the simplification ever bound; it did not.
- **Three outcomes only** — completed, exception, budget exhausted. The last two raise.
  No recovery and no excluded bucket, because a harness that keeps going hides its own
  bugs.
- **The scorer is reimplemented, not borrowed.** AgentBench's harness is not used, only
  its `dev.jsonl`, because transaction-boundary control is the variable under study.
- **The trace captures maximally and derives narrowly.** Runs append raw records; the
  reported counters are a pure function over them, so a new question can be asked of
  old traces.

## Traces

Every run writes `runs/<model>/<task_id>.<mode>.jsonl` — a header with the held-fixed
config, one record per tool call, and a result record with both hashes. Lines are
flushed as they are written, so a run that dies mid-task still leaves an analysable
prefix.

```python
from src.utils.trace import compare_modes, load, summarize
from pathlib import Path

summaries = [summarize(load(p)) for p in Path("runs/qwen2.5-7b").glob("*.jsonl")]
compare_modes(summaries)   # tasks each mode passed and the other did not
```

## Notes

- All 40 modification tasks are single-table with every column typed `TEXT`, and
  identifiers contain spaces — every one must be backticked.
- `answer_md5` is the repr of a Python list. `pymysql` returns a tuple, so the scorer
  wraps `fetchall()` in `list()`; without it every task fails on formatting alone.
- The agent reaches the database only through `execute_sql`, which is checked against an
  allowlist (`SELECT`, `INSERT`, `UPDATE`, `DELETE`). DDL and transaction control are
  rejected — they would implicitly commit and silently destroy the savepoint. An
  allowlist rather than a blocklist, so unparseable input fails closed.
- Held fixed across both arms: model, base prompt, task order, `max_steps`, `max_tokens`
  and the guard. Sampling parameters are left at provider defaults and are identical
  across arms. The prompt is treated as a control — changed deliberately and
  symmetrically before a measured run, never in reaction to results.
- Six harness bugs were found and fixed during development, each of which had produced a
  number that looked like data: a trace written after `cur.execute()` so failing
  statements logged nothing; three classes of raise that bypassed the trace entirely; a
  shared `TASK_DB` letting concurrent runs `DROP DATABASE` on each other mid-task; empty
  hash fields making failures undiagnosable; batched tool calls being rejected; and
  unsanitised control characters. Provider errors escaping before any trace record is
  written is a known remaining gap.
