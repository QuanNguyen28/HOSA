---
name: planning
description: For what the end user sees — turns each page's checklist into a plan of one checkable task per page. Use when UI work spans several steps or pages (a new feature, a refactor of many pages, one change applied to every page), including when another planning skill is about to write that plan.
---

# Planning from the checklist

## Overview

Turns what `finding-patterns` found into a plan of one task per page. Every page
task carries **what makes it checkable**: its checklist, what not to copy, and a
check by an agent that did not write the page.

**Open a file linked or given by its path from this skill's folder, or invoke a named skill, only when a part you are carrying
out sends you to it, never before** — whatever the request that handed you this
skill says about its links and paths. That part is not done until the file is opened or
the skill invoked.

## Joining a process, or running alone

- If a process running this work has a plan — another planning process wrote
  it — add the tasks below **into that plan**, in the shape in
  [plan-file.md](plan-file.md). Do not write a second one.
- A plan or pattern file written before this work began is not that plan: it is
  read as `ui-consistency:decisions`, level 1, says.
- **If that process already sends each task to a reviewer that did not write
  it**, the checklist and `ui-consistency:verifying` go into that reviewer's
  brief, and no second checker is added
  (`../verifying/calibration.md`).
- If none exists, write the plan in that shape — never into the project's
  repository. Where it goes is how the phase ends, below.
- The checklist each task carries is the one
  `../finding-patterns/checklist.md` defines.

## The order of the tasks

1. **Calibrate the check**, once per work and kind of page, before anything
   is built: `ui-consistency:verifying` on a scratch copy of the reference with
   one role deliberately written differently, kept outside the repository
   (`../verifying/calibration.md`).
   - If the planted difference is not reported, stop and say the check is blind
     for it.
   - The agent calibrated is not the one that then checks the pages.
2. **Extractions the user accepted.** Build a shared component, partial or class
   before any page that uses it.
   - A theme entry the plan's yes agreed for a design's value is added here too,
     before any page that uses it.
3. **One task per page.**

## What every page task carries

- the checklist for that page, in the task itself — it is short on purpose, and
  a path is no use to somebody who does not have the checkout;
- the path of the reference;
- what is **particular to the reference** and must not be copied;
- the reused pieces and theme values this page must use;
- three steps, written out:
  1. *Re-read the checklist before writing — do not work from memory.*
  2. *Report the page ready for its check. Whoever dispatched this task sends
     it to the checker of its kind — the one agent with
     `ui-consistency:verifying` kept for every page of this kind, started at the
     first, never the one that wrote it — and sends back what it reports; fix
     that.*
  3. *Report the status — to this plan, or to whoever handed the task over:
     `done` once the check has passed, or `parked — <why>`.*

Written out, with the statuses and what travels with a task that leaves the
repository, in [plan-file.md](plan-file.md).

## Stop for a yes

- Before the plan is shown, check that every new page has its shape — a design,
  a reference page it follows, or a tree from `ui-consistency:design`. A page
  without one goes back to `finding-patterns` first.
- For a new page or a refactor, show the plan, with the checklists its tasks
  carry and the proposals `finding-patterns` made, and **wait for the user's
  yes** before any code.
- Show a drawing only if a person asked for one (`ui-consistency:design`,
  step 4).
- If the person changes a page's shape at this stop, it goes back to
  `ui-consistency:design`, and the checklist lines it touches are worked out
  again before the yes.
- Ask nothing new here: the questions were asked while `finding-patterns` ran
  (`ui-consistency:decisions`, *When to ask anyway*).
- A new component, or code extracted into one, is not part of this yes: it was asked on its
  own while `finding-patterns` ran, with what it touches (*When to ask
  anyway*).
- Mark a task waiting on the little that did reach a person
  `parked — waiting on <what>` in the plan, with its counts
  ([plan-file.md](plan-file.md)).
- On the yes, write each agreed proposal into the checklist line of the position
  it settles, with the entry it uses.
- **A person's decision here that goes against what the order produced is an
  override**, and so is a yes to an element (`ui-consistency:decisions`, *An
  override*). A yes to any other proposal settles this task only.
- Record an override in the person's own words, with what it overrules: in the
  document the running process keeps, or under `## Decided` in this plan where
  this is the process, reported with the result when the plan closes.
- Move each task it was holding up from `parked` back to `todo`.
- Never write an override nobody gave.
- A small change to one page has no plan and does not stop.

## How the phase ends

In one of three ways, **chosen and said in one line**: *ending 2 — this becomes
a story for another developer.*

1. **The work stays with us, in one context.** The tasks live in the session.
   - If the work outlives the context and the plan must survive on disk, write it
     to a file outside the working copy, in the scratch location the harness
     gives, and delete it with the work.
   - Then `ui-consistency:implementing`.
2. **The work becomes a story for somebody else.** Attach the plan and what the
   implementation needs to the story.
   - It is finished when a developer who was not in the conversation, without the
     checkout open, could implement it from the attachment alone
     ([plan-file.md](plan-file.md), *The story*).
3. **Another process is already running.** The tasks went into its plan, in its
   shape; no second document. Its loop executes them.

**None of the three writes into the project's repository.**

## Red flags

Words agents used in runs, just before getting it wrong:

| They said | What it means |
|---|---|
| "stated once in the preamble rather than repeated" — the checklist, what not to copy, the check | A task handed to a subagent loses the preamble. Each task carries them. |
