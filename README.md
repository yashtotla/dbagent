# dbagent

Starter task for Prof. Kexin Rong's group (Georgia Tech): **Database Agent with Exploration**.

An agent runs DBBench modification tasks against MySQL in two modes:

- **Mode A** — every statement commits. A wrong modification cannot be undone.
- **Mode B** — the agent may `checkpoint` before a risky write and `restore` to undo it.

Both modes share one model, one prompt, one guard and one step budget. Only the
checkpoint mechanism differs.

## Setup

MySQL 8 in Docker:

```bash
docker run -d --name dbbench-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=pw mysql:8
```

Python via [uv](https://docs.astral.sh/uv/), and API keys:

```bash
uv sync
cp .env.example .env    # then fill in GROQ_API_KEY
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
| `qwen3.6-27b` | `qwen/qwen3.6-27b` | Groq |

Runs are serial by design — savepoints are session-scoped. Two runs at once are safe
(`TASK_DB` is per-process) but each still needs its own MySQL connection.

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
runs/              one JSONL trace per task per mode, grouped by model
```

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
  rejected — they would implicitly commit and silently destroy the savepoint.
