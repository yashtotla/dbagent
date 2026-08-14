# Flat `restore()` chosen for the MVP; the deferral justified by measurement, not difficulty

Yash scoped `restore()` down to a zero-argument call returning to the most recent checkpoint, and
asked directly whether MVP-first is "the wrong way to go about it for a research problem." The
decision is right and was endorsed; the reasoning needed strengthening, and the question deserved
a real answer rather than reassurance.

**What was verified before answering** (MySQL 8.4.11, live):

1. Repeated flat restores across three nested savepoints walk the stack correctly —
   `L3 → L2 → L1 → original`. A flat `restore()` therefore reaches **any ancestor** via repeated
   calls.
2. A single savepoint survives repeated rollbacks to it — try A → restore → try B → restore →
   try C → restore, all returning `'original'`.

**Why that changes the framing.** Yash's stated justification was "hard to reason about trivially,
hence left out." The true justification is stronger: flat restore is **expressively complete under
stack discipline**, so the handle is a *step-count optimization* (k calls instead of 1 for a
k-level jump), not a capability. Result 2 matters more still — it covers the exact
N-alternatives-at-one-decision-point pattern Yash himself described when refuting the placebo
([[0003-placebo-control-refuted]]), and that pattern needs **one** checkpoint and zero handles. The
MVP fully serves the phenomenon the project studies.

This is the recurring pattern in a new setting: right decision, under-specified reasoning — see
[[0005-mechanism-decided-savepoint]] and [[0002-ddl-guard-is-necessary-but-not-sufficient]]. What is
new is that he *asked* whether the reasoning was sound rather than asserting it, which is the
correct instinct and worth reinforcing.

**The answer to the research-methods question.** MVP-first is not wrong for research. What separates
a defensible research MVP from a lazy one is that the simplification's cost is **measured rather
than assumed**. Concretely: log **checkpoint depth per task**. If the agent never exceeds depth 1
across all 40 tasks, multi-level backtracking was never reachable and the simplification forfeited
nothing — a measured non-issue instead of an admitted gap, for the price of one integer in the
trace. "We left this out because it was hard" is discounted by reviewers; "we left this out and
confirmed it never bound" is not.

**Design detail settled:** `restore()` rolls back to the most recent checkpoint and *keeps* it
(result 2 makes retry a single call). What that forgoes is going *up* a level, so the deferred
extension is properly named **multi-level backtracking**, reachable later either by pop-semantics
or by an addressable handle.

**Teaching implication.** Whenever a scope cut is proposed, do not just ratify it — check whether
the cut removes reachability or only convenience, and name the cheap measurement that would prove
which. That check is fast, it is the difference between a defensible and an indefensible limitation,
and it is exactly the research skill in the second half of [[MISSION.md]].
