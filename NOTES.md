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

## Lesson 04 — shipped

One concept only, per the pacing rules: **the tool boundary is the only enforcement point**. Led
with the analogy (system prompt = documentation, dispatcher = input validation) before any code.
Probed the design against live MySQL before writing — every claim in the lesson is a verified
result, not a design intention:

| probe | result |
|---|---|
| gold-label leading verbs | INSERT ×20, UPDATE ×20 — allowlist is non-binding |
| `pymysql` multi-statement | rejected by driver, `ProgrammingError 1064` — free second layer |
| substring blocklist vs `INSERT … VALUES ('DROP TABLE x')` | **false positive** — kills the naive approach |
| leading-keyword, no comment stripping, on `/* c */ DROP TABLE t` | extracts `''` |
| → under a **blocklist** | **fails open**, MySQL runs the DROP |
| → under an **allowlist** | **fails closed** |
| end-to-end guarded vs unguarded | unguarded: rollback FAILED, `'tentative'` · guarded: rollback succeeded, `'original'` |

The allowlist-vs-blocklist asymmetry is the sharpest thing in the lesson and it lands personally:
an allowlist is the *structural* fix for Yash's recorded weakness of under-enumerating categories
([[learning-records/0002-ddl-guard-is-necessary-but-not-sufficient.md]]) — it doesn't require
thinking of everything. Said so explicitly in the lesson.

`assets/sql_guard.py` — 20/20 cases, 0/40 gold labels blocked, written to be lifted into
`src/dbagent/`.

**Loaded the `claude-api` skill** rather than writing tool definitions from memory. Two payoffs:
Anthropic's agent-design guidance names **reversibility** as the criterion for promoting an action
to a dedicated tool — the project's thesis arriving from the other direction, worth a line in the
write-up. And it surfaced a live error in `CLAUDE.md`.

**Correction to `CLAUDE.md` § Experiment hygiene:** the controls list says "same temperature," but
`temperature`/`top_p`/`top_k` are no longer accepted on current Claude models — they return a 400.
Temperature cannot be held fixed because it cannot be set. Replacements are
`output_config={"effort": …}` and the `thinking` setting. Flagged in Lesson 04 and Reference 05,
with an instruction to verify against the docs for whichever model he pins. **`CLAUDE.md` itself is
his file on `main` — do not edit it; he decides.**

## Lesson 04 — corrected (same session)

Yash accepted the allowlist argument and then audited its *contents*. Two corrections, both mine:

1. **`DELETE` is a DBBench modification type, not my judgment call.** Verified in AgentBench's
   `task.py` — branches on `("INSERT", "DELETE", "UPDATE")` in two places. Dev split has 20/20/0.
   My error: writing "all 40 gold labels are INSERT or UPDATE" (true) and letting it stand in for
   the benchmark's category definition (false). **A split's contents are not a benchmark's schema.**
2. **"Doesn't the agent need SAVEPOINT/COMMIT/ROLLBACK?"** Yes — rejecting them routes the
   capability to `checkpoint()` / `restore(handle)` / `commit_final_answer()`. That's the lesson's
   own bash-vs-dedicated-tool distinction one level in, and the lesson failed to say so.

Both fixed in place with the correction shown. Added the Mode B tool-surface table to the lesson
and Reference 05. See [[learning-records/0006-delete-is-a-first-class-modification-type.md]].

**Rules from this:** never present a benchmark-derived constant as a judgment call without checking
the benchmark's source; and when a guard rejects something the agent plausibly needs, say in the
same breath where the capability went — a rejection list without its routing table reads as a
capability list.

## Decision — flat `restore()` for the MVP, 2026-08-14

**MVP:** `restore()` takes no argument. It rolls back to the most recent checkpoint and **keeps**
that savepoint, so retrying alternatives at one decision point costs one call each.

**Deferred to a post-MVP extension:** multi-level backtracking — going *up* past the most recent
checkpoint. Two ways to add it later, same capability: pop-semantics on `restore()` (walk up one
level per call) or an addressable `restore(handle)` (jump directly).

**Justify it this way, not the other way.** Yash originally framed the deferral as "hard to reason
about trivially." The stronger and true justification, verified on MySQL 8.4.11:

| test | result |
|---|---|
| repeated flat restores across three nested savepoints | `L3 → L2 → L1 → original` — reaches any ancestor |
| one savepoint, three alternatives tried against it | all three return `'original'` — the savepoint survives repeated rollbacks |

So flat restore is **expressively complete under stack discipline**; the handle is a step-count
optimization (k calls instead of 1 for a k-level jump), not a capability. And the second result
covers the exact N-alternatives-at-one-decision-point pattern that motivated Mode B in the first
place — zero handles needed.

**The measurement that closes the limitation:** log **checkpoint depth per task**. If the agent
never exceeds depth 1 across all 40 tasks, multi-level backtracking was never reachable and the
simplification forfeited nothing — a measured non-issue rather than an admitted gap. One integer
in the trace.

This is a *project* decision; it belongs in the write-up's limitations section, not only here.
See [[learning-records/0007-flat-restore-mvp.md]].

## Decision — step = LLM call; parallel tool use OFF, 2026-08-14

Yash forced the definition before engaging with the rejection-costs-a-step question. **A step is an
LLM call, not a tool call**, and DB operations are uncapped. Both right — and structural, since
parallel tool use is on by default and one assistant message may carry several `tool_use` blocks.

**But it must be disabled here.** `checkpoint`/`execute_sql`/`restore` mutate one open transaction
in sequence on one connection; blocks in a single message carry no ordering guarantee. Set
`tool_choice={"type": "auto", "disable_parallel_tool_use": True}` — identically in both modes.
Then one LLM call = one tool call = one DB statement, by enforcement rather than assumption.

**The consequence resolves lesson 03's planted claim.** Exploration is serial in LLM calls (observe
before choosing the next branch), so a 3-alternative exploration ≈ 10 turns ≈ 20,000 ms against
3 restores ≈ 2 ms — **four orders of magnitude**. The "10 branches per turn" column is not merely
unmeasured, it is **structurally unreachable** in this design. Fine-grained branching needs
model-free branching: programmatic tool calling, or a search harness that explores without sampling.

**Write-up claim this unlocks:** *mechanism latency is irrelevant in a serial agent loop and
decisive only under model-free branching* — a regime boundary, stronger than confirming or denying
the paper. See [[learning-records/0008-step-is-an-llm-call-and-what-follows.md]].

Reference 03 and Reference 05 updated with the caveat and the `disable_parallel_tool_use` setting.

## Lesson 05 — shipped

One concept: **design the trace backwards from the claims you intend to make.** Analogy first
(a schema modelled on entities that can't answer the product's queries — his world). The hook is
the same shape as lessons 02 and 04: `CLAUDE.md` states the requirement correctly ("aggregate
numbers alone will not answer … that requires naming specific tasks") and then specifies
`(step, sql, response, latency)`, which **cannot answer it** — no `mode` (runs can't be paired),
no `passed` (recovery undetectable), no `event` type (checkpoint/restore/rejection inexpressible),
no `depth`, and one merged latency where the cost argument needs two.

Every decision from the last three sessions became a schema field, which is the point worth making:
`db_ms`/`llm_ms` split exists only because he defined a step as an LLM call; `depth` exists only
because he cut restore to flat. A trace designed before those decisions would have lost both
arguments.

`assets/trace.py` — `TraceWriter` + `summarize` / `compare_modes` / `narrate`, one analysis
function per write-up sentence. Demo runs on **synthetic** data (labelled as such, no API calls) and
prints `Checkpointing recovered: ['task_19']` plus the narrated case — i.e. the deliverable's own
sentence, generated from the trace.

Reference 06 is the printable version.

**Habit taught:** write the analysis script before the run. If it executes end-to-end on synthetic
data the schema is sufficient; if it needs an unplanned field you learned that for free.

**Contestable claim planted:** one file per `(task, mode)` versus one per task with a mode field.
Chosen so a re-run of one arm can't corrupt the other and pairing is a filename join — but it makes
side-by-side failure analysis a two-file operation, which is the thing he'll actually be doing.

### Lesson 05 — refuted and rewritten, same session

Yash rejected the whole premise: "in my experience, that is the wrong model. We should log
everything and construct an object that uses data from the run to produce some pre agreed fields."
He is right. The lesson conflated a **sufficiency check** with a **capture policy**, and presented
minimality as a virtue when the asymmetry is decisive — an unnecessary field costs bytes, a missing
one costs a re-run.

His framing of the failure mode is exact: *"we are assuming so much about the observations that we
may or may not see."* He also caught that the lesson broke its own "store events, derive counters"
rule by curating which events were allowed to exist.

**The critique caught a real measurement error.** The curated schema had no `stop_reason`, so a Mode
B run truncated at `max_tokens` was indistinguishable from a wrong answer — and would have been
reported as "Mode A recovered a task Mode B lost." Directional, too: Mode B takes more steps →
more tokens → truncates more often, so the artifact penalises the arm under study. Also dropped:
`usage`, assistant `content` blocks, verbatim `db_error`.

Rewritten around his two-layer model. `assets/trace.py` now captures the full API response and
`compare_modes()` **excludes** truncated/refused/incomplete runs and reports them separately. The
demo shows `task_31` being dropped as an artifact rather than scored. Reference 06 rewritten to
match. See [[learning-records/0009-capture-everything-derive-narrowly.md]].

**What survives of the backwards check:** it finds what must be *decided*, not what must be
*captured* — mode label, scorer verdict, held-fixed config, prompt hash. Four commitments;
everything else is capture.

**Standing rule from this:** stop defaulting to minimality. Where capture is cheap and re-obtaining
is expensive, maximal capture plus a derived view is correct. Twice now
([[learning-records/0003-placebo-control-refuted.md]] and this) he has refuted a design that traded
observability for tidiness — flag that trade explicitly when making it, because it is where he
reliably finds the flaw and is reliably right.

## Deferred by design — mining the paper for derived signals

Yash's idea, and a good one: take metric ideas from Xu et al. for the derived layer. **Deliberately
not done now** — derived signals are pure functions of the raw log, so this costs nothing after the
run and constrains nothing before it. Worth noting to him that his own architecture is what made
this deferrable; under the curated schema it would have been urgent.

## Open decision — the write-up's spine, now ripe

`CLAUDE.md` leaves this open and says not to resolve it unilaterally. Raised with him, not decided.
The argument for deciding *before* the run:

- **The two-mode spine can produce nothing.** Single-statement tasks; if A scores 38/40 and B 39/40
  there is one discordant pair and no reportable difference (Reference 02 threshold: ~6 clean flips).
  That is a plausible outcome, not a pessimistic one.
- **The regime-boundary spine is robust to that.** "Mechanism latency is irrelevant in a serial
  agent loop (0.01% of wall clock) and decisive only under model-free branching" rests on
  measurements already in hand and holds regardless of how the agent performs.

It changes what the run must produce: under the second spine the traces carry the argument and named
cases matter more than the score. **His call — do not resolve it for him.**

## Lesson 06 — shipped

One concept: **the loop is trivial; the boundaries are the experiment.** Analogy first (a migration
script — the body is easy, what breaks it is the transaction wrapper, the halfway failure, and
whether you verified before or after).

`assets/agent_loop.py` is dry-runnable with a scripted fake model — **no API key, no budget** — and
walks all eight scenarios covering six exit paths. Keep it as the regression test.

Two exits are decisions rather than mechanics, and both follow from things already established:

- **`max_steps` → COMMIT, not rollback.** Mode A's partial work is already committed; discarding
  Mode B's scores the arms under different rules. (Scoring uncommitted state on the same connection
  then rolling back is equivalent — pick one, state it, apply to both.)
- **`end_turn` with no tool call → reprompt once, then stop.** A spinning loop burns the whole
  budget at ~2 s per empty turn. Never appears in testing; appears eventually across 40 tasks.

Reference 07 is the implementation checklist, including a pre-flight list.

**Contestable claim planted, and I think genuinely unresolvable:** the last line of the Mode B
prompt — *"prefer trying an approach and undoing it over reasoning about which approach is
correct."* Without it he may measure an agent that has the tools and ignores them; with it he has
arguably prompted the result into existence. Neither is neutral. Flagged as a stated design
decision for the write-up rather than something to bury in a prompt string.

## Housekeeping

Added `.gitignore` (`__pycache__/`, `*.py[cod]`, `.venv/`, caches, `.DS_Store`) — Yash asked
mid-turn after the dry run left bytecode. **`runs/` deliberately not ignored**: the traces are the
experiment's evidence and the named recovery cases are quoted from them. Note it landed on
`claude/teach` rather than `main`, which breaks the branch convention slightly — it'll carry over on
merge; offered to move it.

### Lesson 06 — refuted and rewritten, same session

Yash cut the six exit paths to three (happy / exception / max-turns) with **no recovery at all**,
and asked how an incomplete task gets scored. Both moves were right.

**The design was built for the wrong phase.** Graceful degradation is for an unattended production
run; this is 40 tasks with him watching, where it converts bugs into data points — the exact failure
lesson 05 warned about, rebuilt into the harness one lesson later. Debugging posture: crash loudly,
every non-happy exit is fixable. Measurement posture comes later and **cannot be designed first**,
because which failures are irreducible isn't known yet.

**His question dissolves, and that became the lesson's spine.** The scorer is one `SELECT` hashing
rows — it cannot tell whether an agent ran, finished, or used thirty turns. There is no
"scoring an incomplete task" rule; there's only what's on the table when you hash it, and on
outcomes 2 and 3 you never get there. *You don't score tasks, you hash tables.* The whole
"COMMIT don't roll back at max_steps" section went with it.

Kept: `strict=True` by default so the agent's own bad SQL also raises (broken SQL during development
usually means the prompt is wrong); flip to `strict=False` once clean. **Capture maximally, handle
minimally** — the trace is still written up to the crash, which is how debugging works.

**Pacing failure too.** He said "there is a lot I don't understand" — lesson 06 shipped with four
concepts against a rule of one. Rewrite is ~8 min, one idea. The rule keeps breaking on
assembly-shaped lessons; fix is to find the spine first and cut whatever doesn't hang off it.

See [[learning-records/0010-crash-early-and-scoring-dissolved.md]].

**Third instance of the same pattern** ([[learning-records/0003-placebo-control-refuted.md]],
[[learning-records/0009-capture-everything-derive-narrowly.md]], this): each time I traded contact
with observable reality for a cleaner pre-specified structure. **The tell:** a design that starts
enumerating categories of failure and assigning each a handler — that's the moment to ask whether
the categories are known yet.

## Lesson 07 — probably not needed

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
