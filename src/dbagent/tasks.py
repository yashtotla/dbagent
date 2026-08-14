"""Loading the DBBench dev split."""

import json

MODIFICATION_TYPES = ("INSERT", "UPDATE", "DELETE")


def load_modification_tasks(path: str = "data/dev.jsonl") -> list[dict]:
    """Return the modification tasks, each tagged with its dev.jsonl row index as task_id."""
    with open(path) as f:
        rows = [json.loads(line) for line in f]

    tasks = []
    for i, row in enumerate(rows):
        if row["type"][0] in MODIFICATION_TYPES:
            row["task_id"] = f"task_{i:02d}"
            tasks.append(row)
    return tasks


def columns(task: dict) -> list[str]:
    """Return the table's column names in declaration order."""
    return [c["name"] for c in task["table"]["table_info"]["columns"]]


def table_name(task: dict) -> str:
    """Return the table's name."""
    return task["table"]["table_name"]
