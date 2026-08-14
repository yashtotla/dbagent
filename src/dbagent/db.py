"""MySQL access for the scorer and the agent loop."""

import pymysql

from .config import DSN, TASK_DB
from .tasks import columns, table_name


def connect() -> pymysql.connections.Connection:
    """Open a MySQL connection."""
    return pymysql.connect(**DSN)


def build_table(cur, task: dict) -> tuple[str, list[str]]:
    """Recreate the task database, create the task's table, and insert its rows."""
    name, cols = table_name(task), columns(task)
    rows = task["table"]["table_info"]["rows"]

    cur.execute(f"DROP DATABASE IF EXISTS `{TASK_DB}`")
    cur.execute(f"CREATE DATABASE `{TASK_DB}`")
    cur.execute(f"USE `{TASK_DB}`")

    coldef = ", ".join(f"`{c}` TEXT" for c in cols)
    cur.execute(f"CREATE TABLE IF NOT EXISTS `{name}` ({coldef})")

    if rows:
        one = "(" + ", ".join(["%s"] * len(cols)) + ")"
        placeholders = ", ".join([one] * len(rows))
        colnames = ", ".join(f"`{c}`" for c in cols)
        flat = [v for row in rows for v in row]
        cur.execute(f"INSERT INTO `{name}` ({colnames}) VALUES {placeholders}", flat)

    return name, cols


def hash_table(cur, name: str, cols: list[str]) -> str:
    """Hash the table's contents, insensitive to row order."""
    concat = ", ".join(f"`{c}`" for c in cols)
    cur.execute(
        f"SELECT md5(group_concat(rowhash ORDER BY rowhash)) AS hash FROM ("
        f"  SELECT substring(MD5(CONCAT_WS(',', {concat})), 1, 5) AS rowhash"
        f"  FROM `{name}`"
        f") AS sub"
    )
    # pymysql returns a tuple; answer_md5 is the repr of a list. Without list()
    # all 40 tasks fail on formatting with a byte-identical MD5.
    return str(list(cur.fetchall()))


def drop_task_db(cur) -> None:
    """Drop the task database."""
    cur.execute(f"DROP DATABASE IF EXISTS `{TASK_DB}`")
