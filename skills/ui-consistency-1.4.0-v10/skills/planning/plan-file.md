# The plan

**Read when:** writing a plan, or adding its tasks to another process's plan
(`planning`), or executing one of its tasks (`implementing`).

The shape of the plan `planning` writes when no other process wrote one.

## Contents

- The shape
- Every task stands alone
- When the work is done
- The story

**Nothing of it is written into the project's repository** — not committed, not
left in the working copy, not a directory the project is asked to ignore.

**It lives as long as the work, and no longer**, in one of three places — the
three ways `planning` ends ([SKILL.md](SKILL.md), *How the phase ends*):

1. **In the session**, while the work stays in one context.
   - If the work outlives the context and the plan must survive on disk, a file
     **outside the working copy** — the scratch location the harness gives —
     deleted with the work.
2. **Attached to a story** somebody else will implement — *The story*, below.
3. **Inside another process's plan**, in its shape.

**Where a plan already exists**, this is the shape of what is *added into it* —
the tasks, with everything each one carries, and a decision a person made against
the order. Never a second document.

## The shape

````markdown
---
topic: <what this plan is for>
reference: <path to the reference page>
written: <date>
---

# <Topic>

Status of a task: unticked is `todo`, ticked is `done`, and `parked — <why>`
stays unticked with its reason on the line. A page that genuinely should not follow
the checklist is parked with its reason, never forced and never silently skipped.
A task waiting on a question that waits on a person — a new component, code
extracted into one, a tie whose answer changes code outside this work, or a
request that says two things at one of its positions — is
`parked — waiting on <what>`; there is no list of open questions beside the
tasks.

## Decided

What a person decided against what the order produced — their words, what it
overrules, and when. Nothing else is written here, and nothing here is invented.
Where the plan is deleted with the work, what is here is reported to the person
with the result, since nothing else keeps it.

- <the decision, in the person's words> — overrules <what the order produced> —
  <date>; released: <the tasks that were waiting>

## Tasks

- [ ] **Calibrate the check.** Make a copy of `<reference>` with one role
      deliberately written differently — a temporary worktree outside the
      checkout where the project is a git repository — and hand it to a
      separate agent with `ui-consistency:verifying` and the checklist below,
      told only that the copy differs somewhere. Whoever plants does not check.
      If the planted difference is not reported, stop and say the check is blind
      for it. Once passed, record it here — for which kind, and what the plant
      tested and what no plant tested; page tasks of this kind do not repeat it
      (`../verifying/calibration.md`).
      <the checklist the page tasks carry>
- [ ] **<the extraction the user accepted>** — build `<the shared piece>` in
      `<where it belongs>`, before any page that uses it.
- [ ] **<the theme entry the plan's yes agreed>** — add `<entry>` with
      `<the design's value>` to `<the theme>`, before any page that uses it.
- [ ] **<page>** — write `<path>`, following `<path to the reference>`, against
      the checklist below.
      <the checklist's lines, one per position — checklist.md>
      Must not be copied from the reference: <what is particular to it>.
      Not in this task: <a line of the checklist left out on purpose, and why> — or
      nothing.
      1. Re-read the checklist before writing — do not work from memory.
      2. Report the page ready for its check. Whoever dispatched this task
         sends it to the checker of its kind — the one agent with
         `ui-consistency:verifying` kept for every page of this kind, started at
         the first, never the one that wrote it or the one calibrated — and
         sends back what it reports; fix that.
      3. Report the status here — or, handed on without this plan, to whoever
         handed it over: `done` once the check has passed, or `parked — <why>`.
- [ ] **<page>** — `parked — <why>`
- [ ] **Close the plan** — once every task above is done or parked: report what
      is under `## Decided` with the result, and delete the plan where it was a
      file.
````

## Every task stands alone

A subagent executing a task is given **that task and nothing else**; a preamble
does not travel with it.

- **Put everything [SKILL.md](SKILL.md) *What every page task carries* lists in
  each task**, even when the user asks for one line per page.
- **However many tasks there are.** Never write the checklist once and tell the
  other tasks to *copy it in when picked up*: that is the preamble again, and the
  subagent handed one task does not have it.
- For a person, the tasks' first lines are the summary: the page and its status.
- **A task's prose never narrows its own checklist.** *"Change nothing else"*
  does not take a line off it.
- If a line is left out of this task on purpose — another task owns it, a person
  said so — name it under *Not in this task*, with why, and check the page
  against the checklist without that line.
- A line the prose contradicts without naming it is a line the task still
  carries.
- **A task handed on alone says where its status goes** — this plan, or whoever
  handed it over — so step 3 has somewhere to report.
- A page judged to match already is still a task that carries them: its check is
  how "already matches" becomes known.

## When the work is done

Every task done or parked, and the last check passed: **the plan is closed.**

- **The tasks and their checklists go.**
- **What a person decided is reported** with the result.
- An override outlives the work only where a process keeps decisions
  (`ui-consistency:decisions`, *An override*); this plugin keeps none of its
  own.
- **A file is deleted** where the plan was one.
- **A parked task is not done.** While one is parked, the plan stays open and
  says so in its status line.

## The story

Where the work becomes a story for somebody else, **attach the plan and what the
implementation needs to the story**. One test decides whether the attachment is
finished, and it is the only specification it gets:

> A developer who was not in the conversation, and does not have the checkout
> open, implements the story from the attachment alone.

What that test forces:

- **Every task carries its checklist in full** — the positions with what settled
  each, and what must not be copied. A path into a repository is not an
  attachment.
- **Each checklist's first line says it is a snapshot** of the code as it was read,
  and when.
- **Each new page's agreed shape** — the tree, and the drawing if one was asked
  for.
- **What a person decided goes into the story's own text**, in their words:
  whoever implements it works the plan's counts and decisions out again from
  the code, and the story's text is the request.
- **What was not evaluated is named**, so silence is not read as a pass.
- **The check, written so an agent that never saw the plan can run it**: which
  skill to invoke, what to compare against, and that whoever wrote the page does
  not run it.

**Whoever sends the story decides that it goes** — this says only what it must
carry when it does.

**The code stays authoritative**
(`../finding-patterns/checklist.md`, *A snapshot, and the code
wins*).
