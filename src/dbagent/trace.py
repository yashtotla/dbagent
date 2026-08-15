"""Writing and reading per-task run traces."""

import json
import re
from pathlib import Path

RUNS = Path("runs")


class Trace:
    """Writes one task's run to runs/<task_id>.<mode>.jsonl."""

    def __init__(self, task_id: str, mode: str, **config):
        slug = re.sub(r"[^A-Za-z0-9._-]", "_", config.get("model", "unknown"))
        directory = RUNS / slug
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{task_id}.{mode}.jsonl"
        self.file = self.path.open("w")
        self.n = 0
        self._write({"type": "run", "task_id": task_id, "mode": mode, **config})

    def _write(self, record: dict) -> None:
        self.file.write(json.dumps(record, default=str) + "\n")
        # A run that dies mid-task must still leave an analysable prefix.
        self.file.flush()

    def step(self, event: str, response=None, **fields) -> None:
        """Record one agent turn."""
        self.n += 1
        record = {"type": "step", "n": self.n, "event": event, **fields}
        if response is not None:
            record["usage"] = response.usage.model_dump() if response.usage else None
            if response.choices:
                choice = response.choices[0]
                record["finish_reason"] = choice.finish_reason
                record["message"] = choice.message.model_dump()
            else:
                # Provider returned an error payload shaped like a completion.
                record["raw_response"] = response.model_dump()
        self._write(record)

    def result(self, passed: bool, hash_got: str, hash_want: str) -> None:
        """Record the outcome and close the file."""
        self._write({"type": "result", "passed": passed, "steps": self.n,
                     "hash_got": hash_got, "hash_want": hash_want})
        self.file.close()


def load(path) -> list[dict]:
    """Read one trace file."""
    with Path(path).open() as f:
        return [json.loads(line) for line in f]


def summarize(records: list[dict]) -> dict:
    """Reduce one run to the counters the write-up needs."""
    run = records[0]
    steps = [r for r in records if r["type"] == "step"]
    result = next((r for r in records if r["type"] == "result"), None)
    depths = [s["depth"] for s in steps if s.get("depth") is not None]
    usage = [s["usage"] for s in steps if s.get("usage")]
    return {
        "task_id": run["task_id"],
        "mode": run["mode"],
        "passed": result["passed"] if result else None,
        "steps": len(steps),
        "checkpoints": sum(s["event"] == "checkpoint" for s in steps),
        "restores": sum(s["event"] == "restore" for s in steps),
        "rejections": sum(s["event"] == "rejected" for s in steps),
        "max_depth": max(depths, default=0),
        "llm_ms": round(sum(s.get("llm_ms") or 0 for s in steps)),
        "db_ms": round(sum(s.get("db_ms") or 0 for s in steps), 2),
        "out_tokens": sum(u.get("completion_tokens", 0) for u in usage),
    }


def compare_modes(summaries: list[dict]) -> dict:
    """Return the task ids where each mode succeeded and the other did not."""
    by_task: dict[str, dict] = {}
    for s in summaries:
        by_task.setdefault(s["task_id"], {})[s["mode"]] = s
    paired = {t: m for t, m in by_task.items() if "A" in m and "B" in m}
    return {
        "paired": len(paired),
        "b_recovered": sorted(t for t, m in paired.items()
                              if m["B"]["passed"] and not m["A"]["passed"]),
        "a_only": sorted(t for t, m in paired.items()
                         if m["A"]["passed"] and not m["B"]["passed"]),
    }
