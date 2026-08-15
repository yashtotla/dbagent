# dbagent

Starter task for Prof. Kexin Rong's group (Georgia Tech): **Database Agent with
Exploration**. An agent runs DBBench modification tasks against MySQL in two modes —
Mode A commits every statement, Mode B may checkpoint and restore — and we compare them.

Deliverable is a 1–2 page write-up:

1. How checkpointing and restore were implemented, and what the overhead is.
2. Cases where checkpointing enables recovery that linear execution cannot.
3. What I would do differently with more time.

The grading signal is explicitly *approach*, not polish.

Reference paper: *Toward Systems Foundations for Agentic Exploration*, arXiv 2510.05556.
It names three restoration primitives — replay-to-node, snapshot/restore, and
backtracking via compensating operations — and argues all three are too slow, calling for
a native fork primitive. It covers **mechanism, not policy**: it never asks what tells an
agent it should revert.

Setup, commands and layout are in `README.md`.

## Working agreement

- Yash writes the write-up. Every word of it. Claude does not draft its prose and does not
  produce outline bullets that become its skeleton.
- Claude is a full collaborator on the code.
- Yash runs `git commit` himself. Stage and report; do not commit.
- Weekend project. Build the smallest thing that produces an honest number, then analyse
  it. Resist mechanisms, benchmarks or abstractions no question requires.
- One-line docstrings; put a load-bearing "why" in a comment beside the line it explains.
- No constant without a reader, no flag for a question already answered, no abstraction
  for a second caller that does not exist.
- Do not use AgentBench's own harness. Borrow `dev.jsonl` and reimplement the init SQL and
  hashing — transaction-boundary control is the variable under study.
- Short, direct explanations. Examples over jargon.

## Decided

- **Mechanism: `SAVEPOINT` / `ROLLBACK TO SAVEPOINT`.** Measured 0.209 ms with one row
  dirty, 0.646 ms with 44; creating a savepoint is below measurement resolution. Chosen
  because it is the engine-native primitive the paper argues for, and because the
  alternatives are analytically invisible against LLM latency.
- **`restore()` is flat** — returns to the most recent checkpoint and keeps it, so trying
  a second alternative at one decision point costs one call. Multi-level backtracking is
  deferred; log checkpoint depth to show it never bound.
- **A step is one LLM call.** Providers batch tool calls regardless of
  `parallel_tool_calls`, so the loop runs a batch in array order rather than rejecting it.
  Rejecting would penalise Mode B, which batches more because it offers more tools.
- **Three outcomes only:** completed, exception, budget exhausted. The last two raise. No
  recovery, no excluded bucket — during development every non-happy path is a fixable bug,
  and a harness that keeps going hides them.
- **Ordering:** per-task table DDL must finish before `START TRANSACTION`, or its implicit
  commit destroys the savepoint.

## Held fixed across both modes

Model, both prompts, task order, `max_steps`, `max_tokens`, and the SQL guard. Sampling
parameters are left at provider defaults and are identical across arms.

The **prompt is a control**, not a knob. Change it deliberately and symmetrically before a
measured run; never in reaction to results. A prompt statement is legitimate if it states a
property of the environment, and overfitting if it patches an observed failure — the test
is whether it could have been written before seeing a single trace.

## Open

Whether the write-up's spine is the straight two-mode comparison or a sharper argument
about engine-native forking versus the generic mechanisms the paper benchmarks. **Do not
resolve this unilaterally.**
