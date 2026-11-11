# Proving the check can see

**Read when:** dispatching a check — the calibration task of a plan, the check of
a page task, or a small change. It is the dispatcher's: a checker handed a page
does not read it.

Before the checker's result is trusted, show it **a copy of the reference with
one role deliberately written differently** — a different size on a button, a
literal instead of a theme value, its own error message instead of the shared
helper.

- **The one that plants is not the one that looks.** The dispatching agent — or
  the author — makes the copy.
- Tell the checker only that the copy differs from the checklist somewhere —
  never what or where — and not to open the original the copy was made from. An
  agent that plants and checks in one context proves only that it can find what
  it just wrote.
- **Where the copy lives decides what it proves.** In a git repository, make it
  a temporary worktree in a newly created directory outside the checkout, and
  remove it afterwards: imports, the theme and child components resolve, so the
  calibration proves what needs the project.
- Outside a git repository, copy the reference alone into a newly created
  temporary directory. It proves only what one file shows: a class, a literal,
  which helper is called.
- **Say which**, and name what the calibration could not vouch for.
- Never use a fixed, guessable path, and never a copy that could be committed.
- **Calibrate once per work and kind of page.** The calibration proves the check
  — this checklist, this skill, a checker given them — not one agent.
- A later task in the same work, checking a page of the same kind, does not
  repeat it; a new kind owes a new one. A shared piece built for those pages is
  of their kind. The plan's first task is that calibration
  (`../planning/plan-file.md`).
- **The checker of the pages is a new agent**, given the same checklist and the
  same instructions — not the one that was calibrated: that one knows a plant
  exists, and reads the page expecting one. That new agent is the one checker of
  that kind for the work.
- **A change without a plan** owes the proof once, and cheaply: one plant, at the
  position the change touches, in a copy of that one file.
- **Once for the change**: the second round of checking, and any later checker of
  the same page, reuses it.

## When the plant counts

- **A plant counts only when the checker names it as a difference of the page**,
  against the checklist or the family. Found by comparing the copy with its
  original, or reported as something the reference does too, it does not count.
- If the planted difference is not reported, the check is blind for that kind of
  difference. **Say so before anything is built or passed.**
- **Report what the plant tested, and what no plant tested**: *the plant was a
  heading's weight; nothing tested sizes, scrolling or the words.*

## A refactor

The checklist describes the page after the change, so the reference fails it.
Plant in a line the reference already meets, and name the lines the change adds
as unproven.

## A process that already reviews each task

- Where the running process sends each task to a reviewer that did not write it,
  put the checklist and `ui-consistency:verifying` into that reviewer's brief,
  and dispatch no second checker for the tasks. One checker of the kind still
  compares all its pages at the end.
- Calibrate with the same brief. Plant a type role with only part of its bundle
  set — the weight changed, the typeface left as it was: the kind of difference
  a general review passes.
- If the reviewer misses the plant, its check is blind to it: dispatch a
  separate checker again.

## Red flags

Words agents used in runs, just before getting it wrong:

| They said | What it means |
|---|---|
| `mkdir -p /tmp/<name>-$$` for the planted copy | A name anyone can predict, reused if it already exists. Let the system create the directory new — `mktemp -d`, or your harness's own temporary directory. |
