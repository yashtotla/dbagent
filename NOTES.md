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

## Lesson 02 — shipped

Experiment design, built around Milestone 0 as the live exercise. Ran it before writing, which
turned out to matter: the scorer failed **40/40 on correct SQL** because `pymysql` returns a
tuple where AgentBench's driver returned a list, and `answer_md5` is a compared-verbatim repr
string. Real finding, not a constructed example — the lesson is much stronger for it.

Verified results now available to the project (all on MySQL 8.4.11):

- Milestone 0: **40/40** with `str(list(cur.fetchall()))`
- `group_concat_max_len`: default and 1 MB both 40/40; forced to 64 → silent wrong hash.
  Tables are 12–44 rows, truncation starts ≈170. **Bug is real, latent, non-binding.**
- Gold SQL exec: **median 0.92 ms** — the denominator for any checkpoint-cost claim
- 0/40 gold labels contain DDL or transaction-control keywords; all 40 are single statements

`assets/milestone0.py` is the runnable artifact. `build_table()` and `hash_table()` are written
to be lifted into `src/dbagent/` as Yash's own project code.

## Lesson 03 — planned

Measuring restore cost honestly: what to time, what to exclude (process spawn, connection
setup), how many repetitions, and placing `SAVEPOINT` against the paper's seconds-scale table.
Natural follow-on since lesson 02 established 0.92 ms as the denominator.

**Open teaching thread:** the placebo mode (A′) is the lesson's strongest methods claim and also
the most likely thing Yash cuts for time. Lesson 02 deliberately invites him to argue it rather
than accept it. If he defends cutting it, that reasoning belongs in the write-up's limitations —
do not let him drop it silently.
