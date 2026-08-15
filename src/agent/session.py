"""Transaction and savepoint management for one task."""


class Session:
    """Owns the transaction and savepoint stack. Inert in Mode A."""

    def __init__(self, cur, mode: str):
        self.cur = cur
        self.mode = mode
        self.depth = 0
        if mode == "B":
            # build_table must already have run: its DDL implicitly commits,
            # which would destroy sp_0.
            cur.execute("START TRANSACTION")
            cur.execute("SAVEPOINT sp_0")

    def checkpoint(self) -> None:
        """Record a savepoint the agent can return to."""
        self.depth += 1
        self.cur.execute(f"SAVEPOINT sp_{self.depth}")

    def restore(self) -> None:
        """Undo everything since the most recent checkpoint."""
        # Depth is unchanged because the savepoint survives the rollback, so
        # trying a second alternative at the same point costs one call.
        self.cur.execute(f"ROLLBACK TO SAVEPOINT sp_{self.depth}")

    def commit(self) -> None:
        """Commit the task's work. A no-op in Mode A, where each statement already committed."""
        if self.mode == "B":
            self.cur.execute("COMMIT")
