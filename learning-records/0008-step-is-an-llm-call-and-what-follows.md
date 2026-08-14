# "A step is an LLM call" — the distinction that makes the cost argument conditional

Yash forced a definition before accepting the rejection-costs-a-step question: **a step is an LLM
call, not a tool call**, and the agent should not be capped on database operations. Both halves are
right, and the distinction turned out to carry far more than a definition.

**Why it is structural, not definitional.** Parallel tool use is on by default in the Messages API —
a single assistant message may contain several `tool_use` blocks, executed together and returned as
one batch of `tool_result` blocks. LLM calls and tool calls are therefore genuinely different
counters, exactly as he assumed. Budgeting the LLM call is also budgeting the *expensive* unit
(~2 s) rather than the cheap one (gold SQL median 0.92 ms, Reference 03).

**But parallel tool use must be disabled for this project.** `checkpoint` / `execute_sql` /
`restore` mutate one open transaction in sequence on one connection, and blocks within a single
assistant message carry no ordering guarantee — running `restore` concurrently with the `UPDATE` it
should undo is not well-defined. `tool_choice={"type": "auto", "disable_parallel_tool_use": True}`.
With that set, one LLM call = one tool call = one DB statement, and the step becomes unambiguous —
**by enforcement, not by assumption**.

**The consequence, which is the real finding.** Speculative exploration is *serial in LLM calls*:
the agent must observe a branch before choosing the next, and each observation is a model turn. A
three-alternative exploration is therefore roughly 10 LLM turns (~20,000 ms) against 3 restores
(~2 ms) — **four orders of magnitude**. Mechanism latency is not merely small in this design; it is
unmeasurable. Even `docker commit` would be ~7% of the turn budget.

That **resolves the contestable claim planted in lesson 03**. The "10 branches per turn" column is
not just unmeasured — with parallel tool use disabled it is *structurally unreachable*. Fine-grained
branching requires an agent that branches without consulting the model: programmatic tool calling
(a script invoking tools from inside code execution, where only the final result reaches the model's
context), or a search harness that explores without sampling. Both are different system designs from
the one `CLAUDE.md` scopes.

**The write-up claim this unlocks** is a regime boundary rather than a verdict: *restore-mechanism
latency is irrelevant in a serial agent loop and decisive only under model-free branching.* That is
stronger than either confirming or denying Xu et al., because it says **where** their argument
applies.

**Pattern note.** This is the first time Yash has pushed back by demanding a *definition* before
engaging with the question — previously he audited claims and contents
([[0003-placebo-control-refuted]], [[0006-delete-is-a-first-class-modification-type]]) or scoped
decisions ([[0005-mechanism-decided-savepoint]], [[0007-flat-restore-mvp]]). Refusing to answer a
question whose terms are ambiguous is a distinct and more advanced move, and it paid off
immediately here. Reinforce it: when a lesson poses a question, check first whether its terms are
defined, because sometimes the answer is that the question is malformed.
