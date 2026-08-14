# Six exit paths cut to three: crash early, and "scoring an incomplete task" is not a question

Yash rejected lesson 06's harness as over-complex and proposed three cases: happy path, exception,
max-turns — with **no exception handling or recovery whatsoever**, iterating on whatever breaks. He
also asked, plainly, "I don't understand how we will score an incomplete task."

**He is right, and the reason is sharper than simplicity.** The six-exit-path design with an
excluded-artifact bucket is what an *unattended production run* needs. This is 40 tasks with him at
the keyboard. In that setting graceful degradation converts bugs into data points — the exact
failure [[0009-capture-everything-derive-narrowly]] warned about, which I then built into the
harness one lesson later.

**Two postures, and only one is designable now.** Debugging: crash loudly, every non-happy exit is
fixable. Measurement: tolerate whatever survived fixing. The second cannot be designed first,
because which failures are irreducible is not yet known. Best guess after debugging: `max_tokens` is
fixable, `refusal` never fires on this task shape, `end_turn` is rare enough to stop for — leaving
`max_steps`, which is exactly his third case.

**His question dissolves rather than gets answered, and that is the lesson's new spine.** The scorer
is one `SELECT` computing `md5(group_concat(rowhash))` over the table. Nothing in it refers to an
agent — it cannot tell whether one ran, finished, or used thirty turns. So there is no
"scoring an incomplete task" rule to design; there is only *what is on the table when we hash it*,
and on outcomes 2 and 3 you never reach that question because you stopped to look. **You don't score
tasks, you hash tables.** Answering the question as asked would have taught the wrong model; showing
why it cannot be asked is the actual content.

The whole "COMMIT, don't roll back at max_steps" section was deleted with it. It solved a problem
his model deletes — the only case where it mattered was Mode B running out of turns having already
produced the correct state, which is a debugging event.

**Retained, and it is not in tension with crashing:** `strict=True` by default, so the agent's own
bad SQL also raises. Broken SQL during development usually means the prompt or tool description is
wrong. Flip to `strict=False` once the run is clean, and bad SQL becomes an ordinary tool result —
which is the real tool contract. **Capture maximally, handle minimally**: lesson 05 got the first
half right, lesson 06 got the second half wrong, and the trace is still written up to the crash,
which is how the debugging works.

**A pacing failure alongside the design one.** He also said "there is a lot I don't understand."
Lesson 06 shipped with four concepts — ordering, six exit paths, prompt design, dry-run harness —
against a stated rule of one ([[0004-lesson-03-overshot-the-zpd]]). The rewrite is ~8 minutes and
one idea. **The rule keeps getting broken on assembly-shaped lessons**, where there is a lot of true
material and no single obvious spine; the fix is to find the spine first (here: what scoring
actually is) and let the rest hang off it or get cut.

**Pattern, third instance.** [[0003-placebo-control-refuted]], [[0009-capture-everything-derive-narrowly]],
and now this: each time I traded away contact with observable reality for a cleaner pre-specified
structure, and each time he caught it. The tell is consistent — when a design starts enumerating
categories of failure and assigning each a handler, that is the moment to ask whether the categories
are known yet.
