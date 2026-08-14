# Mechanism decided: savepoint only, other three dropped

Yash scoped Mode B down to `SAVEPOINT` / `ROLLBACK TO SAVEPOINT` and closed off replay-prefix,
mysqldump, and docker commit. **The decision is right and was endorsed.** It resolves the choice
`CLAUDE.md` left open and unblocks the agent loop.

**The stated reason was wrong, and was corrected.** He justified it as "one agent run happens in
the same db session, so savepoint is the only relevant option." The premise does not entail the
conclusion — replay-prefix and mysqldump both work fine on a single connection (`DROP DATABASE`,
`CREATE TABLE`, `INSERT` all run in-session). This matters because the justification is headed
for the write-up, where a reviewer would spot the gap.

The reasons that do hold, given to him in place of it:

1. Scope discipline — one mechanism produces the honest number, and scope is explicitly graded.
2. It is the engine-native primitive that Xu et al. argue *for*; choosing it and explaining why
   the generic mechanisms are unnecessary here is a stronger position than benchmarking four.
3. At measured costs (0.646 ms vs 9.4 ms against a ~2 s LLM turn — 0.03% vs 0.5%) a
   savepoint-vs-replay-prefix comparison returns a null result. Retire it with a paragraph citing
   Reference 03 rather than a weekend of runs.

**Two consequences flagged.**

- **The DDL / transaction-control guard is now a correctness requirement, not hygiene.** Dropping
  replay-prefix removes the fallback that could have recovered an agent which emitted DDL. With
  savepoint alone, DDL means silent unrecoverable corruption
  ([[0001-starting-point-and-mission]], lesson 01 branch A). This belongs in the write-up's
  implementation section. Depth not spent on the other mechanisms should go here.
- **It hands him a strong answer to "what state is saved."** Nothing is saved — a savepoint marks
  a position in an undo log InnoDB maintains anyway for crash recovery. That is why checkpoint
  cost measured below resolution, and it is only available because he chose the native mechanism.

**Pattern.** Same shape as [[0002-ddl-guard-is-necessary-but-not-sufficient]]: correct conclusion,
under-specified reasoning. Distinct from [[0003-placebo-control-refuted]], where the reasoning was
the strong part. He converges on good decisions fast; the justification needs a second pass. For a
deliverable graded on *approach*, the justification is the graded artifact — worth saying so
directly.
