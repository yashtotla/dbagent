"""Reject SQL that would silently break the savepoint or the experiment."""

import re

ALLOWED = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})

_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*|#[^\n]*", re.S)
_VERB = re.compile(r"\s*([A-Za-z_]+)")


def is_allowed(sql: str) -> bool:
    """Return whether the statement may run."""
    # Comments are stripped first: "/* x */ DROP TABLE t" yields no verb at all,
    # and an unrecognised verb has to fail closed.
    match = _VERB.match(_COMMENT.sub(" ", sql))
    return bool(match) and match.group(1).upper() in ALLOWED
