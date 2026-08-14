# Placebo control refuted: belief-driven policy makes the decomposition ill-posed

Lesson 02 recommended a placebo arm **A′** — Mode B's tool schema and system prompt, with
`checkpoint()` / `restore()` as no-ops reporting success — to split `B − A` into a prompt effect
and a mechanism effect. Yash refuted it unprompted, and the refutation is correct.

**The argument.** A placebo is valid when the belief being controlled for does not interact with
the mechanism. Here belief drives *policy*: facing three candidate actions, a Mode B agent can
rationally try a cheap guess first precisely because restore is available. An A′ agent inherits
that exploratory policy and then proceeds from corrupted state. A′ is therefore not "Mode A with
a longer prompt" — it is a third condition present in neither arm, and it can score *below* Mode A.

**Sharpening added in session.** A′ also fails on its own terms: if the agent rarely explores,
A′ ≈ A and the control is inert; if it explores often, A′ is actively sabotaged. *Uninformative
when safe, unsafe when informative* — no operating point earns its cost. The additive model
`B − A = [prompt] + [mechanism]` is ill-posed because the prompt's effect is **conditional on**
the mechanism working.

**Resolution.** Mode B is a system (prompt + tools + mechanism); state that and compare two agent
designs, which is what the task asks for. Make the policy change visible instead of netting it
out — branches attempted per task, restores issued, restores that preceded a pass. The clean
control, if time allows, varies *cost* rather than *truthfulness*: savepoint vs replay-prefix,
both of which restore correctly. A′ survives as a separate experiment modelling the lesson-01 DDL
bug ("what does an agent do when its checkpoint silently fails?"), not as a control.

**Second correction, same session.** Yash also caught that "connection lifetime" was miscategorised
as *differs* in the Gate 2 table. Once one connection per task is fixed in both modes it belongs
under *hold fixed*. The real hazard is not the drop but the **silent reconnect** — which destroys
a Mode B branch with no error, the lesson-01 failure mode again. Guidance: no pool, no
`ping(reconnect=True)`, fail loudly and retry the task from the top.

**Implications for teaching.** This inverts the pattern recorded in
[[0002-ddl-guard-is-necessary-but-not-sufficient]] — there Yash under-enumerated a category; here
he found a flaw in a design I had reasoned through and written down. He is now reliably auditing
premises rather than only absorbing them, which is the research half of [[MISSION.md]] working.
Future lessons should plant genuinely contestable claims and invite the audit explicitly, and
should not present any control as settled without stating what the agent believes under it.
