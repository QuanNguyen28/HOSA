# The concept

*What this is, why it is shaped this way, and what it refuses to do.*

## What it is

**An AI-aware design system, read from the implementation.** Every app that has
shipped a few pages has a design system, whether or not anyone drew it: the
components the pages import, the theme and its tokens, the spacing the pages
share, the way forms validate and failures are shown. The team knows it by
working in it. A coding agent does not, and nothing in the repository tells it.
This plugin makes that system readable to the agent at the moment it writes,
from the code itself, with nothing exported or maintained for the purpose.

The way of working is **Design-Driven Development**. What the end user sees
drives the code, the way tests drive it in test-driven development: the page is
read before it is written, and comes out consistent with the rest the first time
instead of being corrected in review.

The design is read wherever it actually lives. Where a page has a design of its
own, a picture or a described screen, its structure is followed and its values
are matched to the theme; one the theme lacks is proposed as a new entry. A
`DESIGN.md` that describes the design system in words is read with the theme.
Where there is no design, the pages already built are the design. That is the
usual case. Tools that make a design system AI-ready usually do it by exporting
it for the agent; this one reads it where it already is.

## The problem

An agent writing UI knows frameworks and component libraries in general. It does
not know **this project**, so it writes pages that work and look wrong:

- the right button, with the wrong variant, size, colour or styles, because it
  never looked at how that button is written in that place on the other pages;
- its own form validation, where the project validates with a library on almost
  every page;
- a new way of catching and showing an error, on every page it writes;
- a literal colour or margin, where the project has a theme;
- a snippet pasted again, where it should have become a component.

Every one of those renders and passes review. Every one is a small, permanent
divergence: the next page is copied from this one.

**This is not a code quality problem.** Linters and type checkers pass on all of
it. It is a *consistency with this project* problem, and the answer lives only in
the repository and in the team's head.

## What was tried first

Tell the agent. A thirty-page refactor with a plan naming exactly which
components to use — and the pages still came out different. A plan is text, and
nothing checked page fifteen against it.

Then programs: parsers, checks, inventories. They became thousands of lines that
kept being wrong on the next project, and debugging them replaced the work they
were meant to support.

## The shape

**Skills the developer's own agent follows, and nothing else.** The agent already
reads code. The skills say how to look — in what order, what to count, how to
decide — and the agent looks with its own tools. That is what makes
Design-Driven Development possible here without a drawing: the design is
recovered from what exists.

The work goes through four phases, the same whether a planning process such as
superpowers is running or not:

1. **Find the pattern** — read a reference page top to bottom and left to right,
   search what the other pages reuse and how, take values from the theme, and
   turn the page's structure into a checklist for the task.
2. **Plan** — one task per page, each carrying what makes it checkable.
3. **Implement** — one page at a time, in a fresh context, from the checklist.
4. **Verify** — a separate agent compares each page with the reference, region by
   region, and then the whole set.

A change to one region of one page takes a shorter phase of its own, which reads
only that position across the pages. Three more skills are called from the
phases when a step needs them: the project's values — theme, spacing, type,
elements — how to count what its pages do, and the order that settles a choice.
Two are asked for on their own or reached from a phase: a page's design, agreed
in words before it is built, and an accessibility standard, measured only when
somebody asks for it or the project states one.

The design has a skill of its own. Where one comes with the work it is read for
the page's structure, and its values are matched to the theme, never written
into a page as they stand. Where there is none and no page is near enough to
follow, the shape is agreed with the person in words, as a tree of the
project's own pieces — and drawn, with the project's values, only when somebody
asks to see it.

With another process running, each phase adds to that process's spec and plan
rather than starting a second one. It tells by what exists on disk, not by which
plugins are installed.

## The ideas everything else follows from

### Roles are universal; names are local

A page has a holder, a header, a content area, fields, a submit button, a way of
showing a failure. Every technology has those roles, and every technology fills
them with different pieces — a framework component, a custom element, a partial,
a block of markup with a shared class. So the skills name roles and read what
fills them from the project. A project of plain HTML and CSS goes through the
same phases.

### A named reference outranks a count, and you can overrule either

Eight pages sharing a convention and eight pages sharing a mistake look
identical to a counter. So a person names the page to follow, and counting only
separates what repeats from what belongs to that page alone. Counts are honest
only with two more facts:

- **where the component stands** — in one app, 10 of 18 buttons were full-width,
  which reads as no rule; by position it was 10 of 10 in the content area and 0
  of 4 in toolbars;
- **how many files** — four identical buttons in one file are one page's habit.

**What naming a page settles, and what it does not.** It settles what the page
*is*: which roles it has, in what order, how it behaves. It does not settle
whether to reach for the project's own shared piece. A page named as the
reference because it is the right shape may have been written before that piece
existed, and copying what it hand-writes would produce the drift this exists to
prevent, with a blessing nobody gave. So the shared piece wins over the copy
inside the reference, and both sides are said in one line.

**An override** is a person's decision against what everything above produced —
*submit buttons are full-width from now on, even though most pages still write
them auto* — the case counting can never reach, because the project is half way
through changing and the majority is the old way. It sits directly under the
request and above a named page, because it is about one concern while a
reference is a pointer at a whole page, and where it is kept it stands until
somebody changes it.

An override is the one thing a task cannot work out again for itself, so it is
the one thing kept — in whatever document the running process already uses for
decisions, never in a file of this plugin's own. With no such process it is
reported with the result, and nothing keeps it. Nothing writes one nobody gave.

### It decides, and says what settled it

Where the reference and the rest of the project agree, the agent takes the answer
and says so. Where they disagree, a written order settles it — the request, an
override somebody gave before, a named page, the shared piece over a private
copy, the newest members, the majority with its file spread, the reference — and
the decision is reported with the level that settled it and the numbers under it.

A question is a thing somebody has to settle by hand, which is the work this
exists to remove, and a tool that interrogates gets switched off. Three things
wait on a person: the plan, shown for a yes before any code; a tie in the order
whose answer changes code outside the task; and a new component the request did
not name with its place, or code extracted into one, asked on its own with what
it touches, since it adds a piece the project did not have. A proposal — a theme entry, a
single place for shared values — and a contradiction the project carries are
reported, with the plan where there is one. A request that says two things at one
position, or leaves open what the page must show, is reported as blocking, and
only the positions it touches wait on the answer.

### A plan carries its check

What failed before was a plan with nothing closing the loop. Here every page task
carries its checklist, what not to copy, and a check by an agent that did not
write the page. Before any of those checks is trusted, whoever hands out the
tasks proves the check can see, once per work and kind of page, on a copy of the
reference with one difference planted.

### Silence is never success

"It found nothing" can mean the pages match, or that nothing was looked at. Every
phase says what it read, whether it sampled, and what it could not interpret.

### Nothing is kept that can be worked out again

A count is true of the code as it was read, and the code moves on. Written to a
file it becomes a thing to review, keep in step between branches and find stale —
and a count nobody notices has gone stale is worse than none. Everything the
order settles is reproducible from the same code, so a task keeps nothing.

One thing is not reproducible: a person overruling the order. That goes wherever
the running process already records what was decided — never into a document of
this plugin's own; with no such process, it is reported with the result.

## What it writes down

- **A checklist**, inside the task: the page's structure as questions, in reading
  order, each line carrying the project's own piece, how it is written and what
  settled it. It goes when the task does.
- **A plan** — only when no other process wrote one, only while the work runs,
  and **never in the project's repository**. Planning ends in one of three ways:
  the work stays in one session, where the plan lives (a scratch file outside the
  working copy if it must outlive the session, deleted with the work); the work
  becomes a story, and the plan is attached to it, complete enough for a
  developer without the conversation or the checkout; or another process is
  running, and the tasks go into its plan. When the work is done, what a person
  decided is reported and the plan goes.
- **A drawing of the page-to-be**, only when somebody asks to see it: one
  self-contained document outside the working copy, drawn with the project's
  values and labelled with its own components. Nothing is ever read back out of
  it.

## What this is not

- **Not the whole job.** Whatever process is running keeps the plan, the tests
  and the logic. This has one subject: what the end user sees, coming out like
  the rest of the project so nobody fixes it by hand afterwards.
- **Not a test suite.** It writes none, and never starts one.
- **Not a linter.** It has no opinion about your code in general.
- **Not a design-system opinion.** It follows *your* vocabulary.
- **Not a gate.** Nothing fails a build.
- **Not a program.** No parser, no network, no telemetry, no account, no key.
- **Not for sale.** Free and open source.
