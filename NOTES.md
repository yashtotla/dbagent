# Teaching notes — working scratchpad

## How Yash wants to be taught

- Short, direct explanations. Examples and parallels over jargon. (Stated in `CLAUDE.md`, and it
  applies to lessons too.)
- Mission has a research-skill half, so **show the method, not just the conclusion**: cite
  primary sources inline, mark unverified claims as unverified, prefer "reproduce this yourself"
  over "trust me."
- Do not draft write-up prose or outline bullets for it. Hard boundary from `CLAUDE.md`. Lessons
  may teach *how* to structure a systems note in general; they must not shape this specific one.

## Workspace conventions

- Lessons link `../assets/lesson.css` and `../assets/quiz.js`. Reference docs link the CSS only.
- Quiz markup contract is documented at the top of `assets/quiz.js`. Options shuffle on load, so
  answer position carries no information on re-read — these are meant to be revisited.
- **Quiz answers must be equal word count** across all options, so length leaks no signal.
- Reference docs are the printable artifacts; lessons are read once or twice. Put the durable
  compression in `reference/`.

## Open threads to pick up

- **Unverified premise:** AgentBench's per-statement `conn.commit()`. Handed to Yash as an action
  item in Lesson 01. Follow up next session — if it turns out false, the project's framing shifts
  significantly and `CLAUDE.md` needs an edit.
- **Undecided, deliberately:** whether the write-up's spine is the plain two-mode comparison or
  the sharper native-forking argument. `CLAUDE.md` says do not resolve unilaterally. Lesson 01
  notes the evidence is tilting toward the second but explicitly leaves the call to Yash.
- **Unmeasured:** `SAVEPOINT` restore latency at DBBench table sizes. No published source exists;
  this has to be measured. Good candidate for a hands-on lesson that doubles as real project work.
- Milestone 0 (40/40 gold-SQL hash check) not started. A lesson on experiment design could use it
  as its live exercise rather than a toy.

## Calibration log

- 2026-08-14 — Lesson 01 pitched at: knows BEGIN/COMMIT, savepoints new. Completed same session,
  no complaints about pace — hold this level for Lesson 02 and push slightly harder.
- 2026-08-14 — Yash reached the DDL-guard conclusion **independently** from the lesson, which is
  the right instinct. He generalised one step too far (treated DDL as the only killer) and fused
  `autocommit` with *implicit commit*. Pattern to watch: extracts the load-bearing rule quickly,
  then under-enumerates the remaining cases. Lessons should include an explicit "what else is in
  this category?" beat rather than trusting the single worked example to generalise.
  See [[learning-records/0002-ddl-guard-is-necessary-but-not-sufficient.md]].

## Lesson 02 — decided

Experiment design, using the confound Yash's own conclusion just created: guarding the agent's
action space in Mode B but not Mode A adds a second variable. Live exercise is Milestone 0
(40/40 gold-SQL hash check) — real project work, not a toy. Container `dbbench-mysql` is already
running (MySQL **8.4.11**, not 8.0).
