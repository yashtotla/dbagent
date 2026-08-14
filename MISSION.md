# Mission: Agentic Exploration & Database Checkpointing

## Why

Yash is doing the "Database Agent with Exploration" starter task for Prof. Kexin Rong's group
at Georgia Tech. The deliverable is a 1–2 page write-up, and the stated grading signal is
*approach* — "to give you a chance to explore the problem and give me a sense of how you
approach an open-ended research and systems problem." So the mission has two halves: produce a
write-up good enough to earn the spot, and build the underlying skill of taking an ambiguous
research question and turning it into an honest, defensible result.

Not "understand checkpointing." **Land the position, by actually doing the research well.**

## Success looks like

- Can state precisely which checkpoint mechanism Mode B uses, why the others were rejected, and
  what each one costs — with measured numbers, not hand-waving.
- Can name specific tasks (by id) where checkpointing recovered a failure that linear execution
  could not, sourced from reading traces rather than aggregate scores.
- Can explain, unprompted, what the experiment *cannot* conclude — and says so in the write-up
  before a reviewer has to ask.
- Can read a systems paper and separate what it measured from what it argued from what it
  assumed.
- Writes every word of the write-up himself, and it reads like his own thinking.

## Constraints

- **Weekend project.** Build the smallest thing that produces an honest number, then analyze it.
  Scope discipline is explicitly part of the grade.
- Claude is a full collaborator on code, and **never drafts write-up prose or its outline** —
  the reviewer is the paper's author and the point is that the thinking is Yash's. See
  `CLAUDE.md` § Working agreement.
- Starting level: comfortable with `BEGIN`/`COMMIT`/`ROLLBACK`; savepoints, isolation levels,
  and implicit-commit rules are fuzzy. Pitch accordingly and rise fast.
- Prefers short, direct explanations. Examples and parallels over jargon.
- Stack is fixed: MySQL 8 in Docker, raw SQL, `pymysql`, `anthropic`. No Postgres, no ORM.

## Out of scope

- The 20 SELECT-family tasks in `dev.jsonl`. Only the 40 modification tasks matter.
- AgentBench's own harness (AgentRL server/client, docker-compose). Reimplement the ~60 lines;
  transaction-boundary control is the variable under study.
- Training, fine-tuning, or model-level work. The agent is a while loop.
- General LLM-agent engineering beyond what this experiment needs.
