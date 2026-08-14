# Lesson 03 overshot: two new things at once, one of them undefined

Yash reported lesson 03 "went over my head." Diagnosis: the lesson introduced **measurement
methodology** (floors, resolution, p50/p95, timed regions) on top of **four restore mechanisms
that had never been explained** — only named, in lesson 01's candidate list and in `CLAUDE.md`.
Two new things at once, one of them undefined. Working memory blown. This is a drafting failure,
not a comprehension failure, and was fixed rather than re-taught.

**What he got right.** Rollback cost scales with rows dirtied since the checkpoint — stated
unprompted and correct (0.209 ms at 1 row, 0.646 ms at 44). The mechanism-level intuition landed.

**Two misconceptions, both traceable to the missing explanation:**

1. **Framing.** He read the benchmark table as "operations involved in a single Mode B run" —
   i.e. stages of one pipeline. They are four *competing designs*; you pick one and build Mode B
   out of it. Without knowing what replay-prefix and docker commit were, a sequential reading is
   the only one available. Fixed with a document-undo analogy (Ctrl+Z / retype from template /
   save a text copy / snapshot the whole computer) ordered as a narrow→broad ladder, which also
   makes the coverage-vs-cost trade self-evident.

2. **Floor inversion.** He described the baseline as "creating a checkpoint (because it is faster
   than `SELECT 1`)." Backwards: the floor is `DO 1`, a statement doing no work, measuring the
   ~0.11 ms fixed tax on any statement. `SAVEPOINT` landing *at* the floor is the **finding**
   (checkpointing is free), not the baseline's definition. He promoted a result to a premise.

**Implications for teaching.** The prior calibration note said "hold this level and push slightly
harder" — that was wrong and produced this. Revised rules:

- **Never benchmark or compare a thing that has not been explained.** Naming it in a prior
  lesson's candidate list does not count as teaching it.
- **One new concept per lesson.** Lesson 03 should have been two: what the mechanisms are, then
  how to time them.
- Concrete analogies land with him; the Ctrl+Z ladder did what three paragraphs of prose had not.
  `NOTES.md` already recorded "examples and parallels over jargon" as a stated preference — that
  should have been applied here and was not.
- Watch for **result-promoted-to-premise** as a recurring pattern. It also explains why the
  savepoint/floor relationship inverted: when a chain is not fully understood, he anchors on the
  most memorable fact and reasons outward from it.

Remediation shipped: `reference/restore-mechanisms.html` (Reference 04) and two inserted sections
in lesson 03 — the four candidates up front, and an explicit definition of the floor.
See [[MISSION.md]], [[0003-placebo-control-refuted]].
