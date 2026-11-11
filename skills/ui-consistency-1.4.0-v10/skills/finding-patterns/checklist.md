# The checklist

**Read when:** writing the checklist (`finding-patterns` step 8), building
against it (`implementing`) or walking it (`verifying`).

A checklist is **the page's own tree turned into questions, in the order the
page is read.**

- It belongs to the task: put it into the task in the plan, or into the document
  the process already running keeps.
- Where there is neither, it lives in the turn and goes with it.
- **Write nothing measured to a file that outlives the work.**

## Contents

- The shape
- Every item carries how, not whether
- Eight to twelve items
- A snapshot, and the code wins

## The shape

````markdown
<page> against <kind> (<what decided the kind>) — from <reference>, <n> members
of <m> candidates in <the bound>, read <date>

- [ ] <role> — <the project's piece>, <how it is written> — <what settled it>
- [ ] <role> — <the project's piece>, <how it is written> — <what settled it>
- [ ] not copied from <reference>: <what is particular to it; and anything it
      hand-writes that the project has a shared piece for>
````

- One line per position, in the order the page is read: the outermost holder
  first, then inward and left to right, then what the user sees happen.
- In the first line, *n* is the family counted and *m* the pages considered
  before non-members were removed (`ui-consistency:conventions`, *Which pages
  are the family*).
- A line's own count is over that position in the members — *4 of 4* pages, or
  *8 of 8* fields where each page has two. **A line whose region has a family of
  its own carries that count instead** — `ui-consistency:conventions`,
  *A family that differs by region*.

An example, filled in:

````markdown
returns against list page (all five render a toolbar and a table of rows, and
src/pages keeps them together) — from orders, 4 members of 5 candidates in the
app, read 2026-09-17

- [ ] page holder — the shared page holder, as its own landmark — 4 of 4, 4 files
- [ ] toolbar in the header, title one level down — 4 of 4, 4 files
- [ ] rows — the shared table, row height on the base — 4 of 4, 4 files
      (the three above: the holder's, the toolbar's and the table's exact names,
      over the 4 members' page files)
- [ ] open row — marked the way shipments marks it (the mechanism), with the
      theme's pale tint the other 3 use (the values)
- [ ] filter control — the shared toggle, showing *on* while a filter applies —
      10 of 14
- [ ] form — validated through the shared helper, not its own — the shared piece,
      against the copy in shipments
- [ ] field — label tied to it, error under it, through the shared field — 8 of 8
- [ ] submit — the shared button, full-width, in the content area — the majority,
      3 of 4 across 4 files
- [ ] request failure — the shared error helper, not a new message box — 3 of 4
- [ ] colour and spacing through the theme; no literal, nothing off the base
- [ ] not copied from orders: its title text, the margin only it has, and its
      own error box — the project has a shared error helper
````

## Every item carries how, not whether

*Is the button there* gets ticked without looking. **The project's own piece, how
it is written, and what settled it** cannot be ticked without opening the page.

- **End each item with the report**: the level of the order that settled it and
  the numbers under it — *the majority, 3 of 4 across 4 files*, *the shared
  piece, against the copy in <page>*, *as asked*. Walking the checklist is then
  also reading every decision that was made (`ui-consistency:decisions`, *Say
  what settled it*).
- *As asked* covers only what the request itself says. How it is done carries
  its own level.
- **Each count carries its search**: the exact names, and the files it ran over,
  so a checker can count it again the same way. A search that served several
  lines is written once, under them.
- **One source for each claim.** Where two precedents could settle a position,
  cite the one that did.
- **A cited precedent says which half it is for** — the mechanism, or the values
  — where the two come from different places.
- **Name the behaviour** — *a click on the row, not on its checkbox or its
  actions, opens the detail*. Name an event or a prop only when that is what was
  counted.
- **A line that names a control says the state it shows**: *pointing down while
  the pane is open*.
- A bare count names no level. After a shared piece — *the shared field — 8 of
  8* — it is level 4, with the piece's use among the members. After anything
  else it is the majority, level 6. Name every other level.
- **If the family is split on whether the role is there at all**, the line
  carries both decisions: *present — the majority, 6 of 8; through the shared
  date picker — the shared piece* (`ui-consistency:conventions`, *Counting
  honestly*).
- **If the family has no convention at a position**, say that on the line
  instead of a number that reads as one: *no convention — three ways across 8
  files; the two newest write it this way* (`ui-consistency:conventions`, *When
  a count is not a convention at all*).

## Eight to twelve items

- Keep to the positions that carry something: a piece the project shares, a
  convention with a count behind it, and what must not be copied.
- **If it will not fit, leave out** anything the technology gives for free,
  anything identical in every page of every kind, and any position where the
  family has no convention — and say out loud that such a position was left
  out.
- **Keep every position the task changes**: a position the work exists to settle
  stays on the checklist, as *no convention*, whatever else is left out.

## A snapshot, and the code wins

- The first line says when it was read.
- If the checklist and the code disagree, the code is right: work the checklist
  out again from the code, never argue with the copy in hand.
- That first line and the short body make it **the extract a task carries out of
  the repository**. What a task takes with it, and who decides that it goes, is
  `../planning/plan-file.md`.
