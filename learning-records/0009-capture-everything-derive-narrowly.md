# Backwards trace design refuted: capture is a separate decision from analysis

Lesson 05 taught deriving the trace schema from the claims the write-up intends to make. Yash
rejected it outright — "in my experience, that is the wrong model" — and proposed the two-layer
alternative: log everything, construct a derived object producing pre-agreed fields, then analyse
each run deeply for anything peculiar. He is right, and the lesson was rewritten rather than patched.

**The precise error.** The lesson conflated a **sufficiency check** with a **capture policy**. "For
each claim, name the field" is a sound way to find what is missing; the lesson then wrote that the
resulting set "is usually smaller than log-everything, and unlike that pile, it is sufficient",
presenting minimality as a virtue. It is not. The asymmetry decides it: an unnecessary field costs
bytes (~800 records for the whole experiment), a missing one costs a re-run. There is no scale here
at which curation pays.

**Yash's framing of the failure mode** — *"we are assuming so much about the observations that we
may or may not see"* — is exact. A schema derived from anticipated claims is structurally blind to
the unanticipated finding, and this deliverable explicitly asks for named cases of behaviour nobody
predicted.

**He also caught that the lesson broke its own rule.** It stated "store events, derive counters" and
then curated which events were permitted to exist. His correction is that same principle one level
up: the events are raw too.

**The critique caught a concrete measurement error, not just a design preference.** The curated
schema omitted `stop_reason`. A Mode B run truncated at `max_tokens` is therefore indistinguishable
from a wrong answer, and would have entered the results as "Mode A recovered a task Mode B lost" — a
fabricated finding in the headline table. Worse, it is **directional**: Mode B takes more steps,
accumulates more tokens, and truncates more often, so the artifact systematically penalises the arm
under study. Three others in the same family were also dropped: `usage` (the whole cost axis),
assistant `content` blocks (where the agent's stated reason for restoring lives), and the driver's
verbatim `db_error`.

**What survives.** The backwards check is still useful, but for a much narrower purpose: it
identifies what must be **decided or arranged** before the run, because logging cannot recover it —
the `mode` label, the scorer verdict, the held-fixed config, and a prompt hash proving no drift.
Four design commitments; everything else is capture.

**Pattern.** This is the second time Yash has refuted a design I had reasoned through and written
down ([[0003-placebo-control-refuted]] was the first), and both refutations share a shape: I
optimised for a clean pre-specified structure and lost contact with what could actually be observed.
He consistently defends the messier, more faithful representation. Worth stating plainly in future
lessons when a design trades observability for tidiness — that trade is where he reliably finds the
flaw, and he is reliably right about it.

**Teaching implication.** Stop presenting minimality as a virtue by default. For anything cheap to
capture and expensive to re-obtain, the correct default is maximal capture with a derived view on
top. Reserve curation arguments for surfaces where capture genuinely costs something.
