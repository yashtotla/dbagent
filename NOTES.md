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

## Lesson 03 — shipped

Measured before writing again, and again the measurement produced the lesson. First run used
`SELECT 1` as the round-trip floor and reported `SAVEPOINT` at **negative cost** — impossible.
Cause: `SELECT 1` returns a result set, `SAVEPOINT` returns an OK packet, so the floor did more
work than the treatment. `DO 1` is the correct no-op. **This is the placebo error at
microbenchmark scale**, and the lesson says so explicitly — a baseline must do the same work as
the treatment minus only the thing being isolated.

Measured on MySQL 8.4.11, `game_results` (44 rows × 5 cols), localhost Docker:

| mechanism | p50 | × vs savepoint |
|---|---|---|
| `DO 1` floor | 0.117 ms | — |
| `SAVEPOINT` | 0.104 ms | below resolution — **checkpointing is free** |
| `ROLLBACK TO SAVEPOINT` 1 row | 0.209 ms | 1× |
| `ROLLBACK TO SAVEPOINT` 44 rows | 0.646 ms | 3× |
| replay-prefix k=0 → k=20 | 6.37 → 9.37 ms | 30–45× |
| mysqldump + reload | 105 ms | 504× |
| `docker commit` | 510 ms (n=3) | 2440× |

Three findings worth the write-up: checkpoint is free and only restore costs; replay-prefix fits
`6.4 ms + 0.15 ms × k` so the fixed reset dominates until k≈42 (**not** "linear in path length"
as `CLAUDE.md` describes it); and `docker commit` at 510 ms independently reproduces the bottom
of Xu et al.'s 0.416–6.915 s Docker range.

**Corrected my own overclaim.** Reference 01 and Lesson 01 both said savepoint is "three to six
orders of magnitude" below the paper's mechanisms. Measured, it is **two to six** — against
CRIU's best case (0.060 s) a 44-row rollback is only ~93×. Fixed in both files with the
correction shown.

## Pacing correction — lesson 03 overshot

Yash reported lesson 03 went over his head. Cause: it introduced measurement methodology on top
of four mechanisms that had only ever been *named*, never explained. Two new concepts at once,
one undefined. My earlier note said "hold this level and push slightly harder" — that was wrong.

**Hard rules from here:**

1. **Never benchmark or compare a thing that has not been explained.** Naming it in a candidate
   list is not teaching it.
2. **One new concept per lesson.** Lesson 03 should have been two lessons.
3. **Lead with a concrete analogy.** The Ctrl+Z / retype-from-template / save-a-copy /
   snapshot-the-computer ladder did in one table what three paragraphs of prose had not. This was
   already recorded as a stated preference and I failed to apply it.
4. **Watch for result-promoted-to-premise.** He described the floor as "creating a checkpoint"
   because `SAVEPOINT` measured at the floor. When a chain is not fully understood he anchors on
   the most memorable fact and reasons outward from it — so state explicitly which items are
   *findings* and which are *definitions*.

Remediation shipped: Reference 04 (`restore-mechanisms.html`) plus two inserted sections in
lesson 03. See [[learning-records/0004-lesson-03-overshot-the-zpd.md]].

## Decision — mechanism is savepoint, 2026-08-14

Yash scoped Mode B to savepoint only. Endorsed; the reasoning was corrected (single-session does
not rule out replay-prefix — it works fine on one connection). `MISSION.md` out-of-scope updated,
Reference 04 carries a decision banner.
See [[learning-records/0005-mechanism-decided-savepoint.md]].

**Recurring pattern now confirmed across three records:** he converges on the right decision fast
and under-specifies the justification. LR 0002 (DDL guard), LR 0005 (mechanism choice). The
exception is LR 0003 (placebo), where the reasoning was the strong part. Since the deliverable is
graded on *approach*, the justification is the graded artifact — say that directly rather than
just supplying the missing reasons.

## Lesson 04 — planned

The agent loop: tool schemas that make branching legible in the trace, and logging that can
answer "which task did checkpointing rescue?" Natural follow-on — lesson 03 established that
overhead scales with *branches per turn*, so the trace has to record branch structure or none of
the cost analysis can be connected to outcomes.

**Now doubles in importance:** dropping replay-prefix removed the fallback for agent-issued DDL,
so the tool boundary is the only thing standing between the agent and silent corruption. The
guard belongs in lesson 04 as a first-class topic, not an aside. One concept, concretely — per
the pacing rules above.

**Contestable claim planted in lesson 03**, flagged as such in the footer: the branches-per-turn
table assumes a 2 s LLM turn and 1-vs-10 branches, neither measured. If Yash's agent branches
once per task, the whole cost argument reframes. He has been told to audit it — see whether he
does unprompted, which is the next signal on the research half of the mission.

**Resolved — placebo mode is dead.** Yash refuted A′ on the session it shipped: belief drives
policy, so a lying no-op restore produces a third condition rather than a control, and can score
below Mode A. Lesson 02 and Reference 02 have been corrected in place, with the correction shown
rather than quietly patched. See [[learning-records/0003-placebo-control-refuted.md]].
Replacement guidance: state that Mode B is a system, measure the policy change (branches per
task, restores issued, restores preceding a pass), and if there is time use savepoint vs
replay-prefix — a control that varies *cost* not *truthfulness*.

## Calibration update — 2026-08-14

Yash has flipped from absorbing to auditing. He caught a design flaw I had reasoned through and
written down, and separately caught a miscategorised row in the Gate 2 table. This is the
research half of the mission working, and it changes how to write lessons:

- **Plant contestable claims deliberately and say they are contestable.** He engages with them.
- **Never present a control as settled** without stating what the agent believes under it.
- Do not soften corrections into "good point, but" — he was right twice; say so and fix the file.
- Pattern still worth watching from [[learning-records/0002-ddl-guard-is-necessary-but-not-sufficient.md]]:
  strong at auditing a claim in front of him, weaker at enumerating the rest of a category
  unprompted. Keep the explicit "what else is in this category?" beat.
