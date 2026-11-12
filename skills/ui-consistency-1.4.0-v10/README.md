# ui-consistency

> [!NOTE]
> **ui-consistency** is in its early stages and under active development. It is
> built entirely using Claude Code. If a page comes out wrong, please
> [tell us what happened](https://github.com/kamenkurtev/ui-consistency/issues/new?template=a_page_came_out_wrong.yml)
> — your agent offers to draft the report, with your project's names made
> neutral. If it helps you, please star the repository: that is how other people
> find it. Thank you for your understanding.

**An AI-aware design system, read from the code you already have.**

Your app already has a design system, even if nobody ever drew one. It lives in
the components every page imports, in the theme and its tokens, in the way four
pages space their sections the same way, in the error helper nobody rewrites.
The people on your team know it because they work in it every day.

Your coding agent doesn't. It has read millions of projects and writes the
average of them, so the button it ships is the wrong variant and one size up.
Two lines under a theme that has `--color-danger`, it hardcodes `#c62828`. The
form validates itself instead of importing the helper every other page imports,
and the failure toast becomes the fourth way your app shows a failure. None of
it errors or fails a lint, so it gets caught in review and fixed by hand, again.

ui-consistency makes your design system visible to the agent. Before it writes a
page, the agent reads how your pages are already built and writes the new one
the same way. Nothing is exported for it and nothing has to be kept in sync:
there is no tokens file to generate and no catalogue to maintain, because the
code is the source.

The way of working behind it is **Design-Driven Development**. What the user
will see drives the code, the way tests drive it in test-driven development, so
the page is meant to come out right the first time instead of being fixed
afterwards. When a page has a design of its own, a picture or a described
screen, the agent follows its structure and matches its values to your theme,
proposing a new theme entry for one your theme lacks. A `DESIGN.md` at your
project's root is read with your theme, and its values are matched the same way.
When a page has no design, the pages you have already shipped are the design.

It names roles rather than components, so React, Vue, Angular, Svelte and plain
HTML and CSS all go through the same steps. There is nothing to configure and no
build step. It joins whatever else you run: your planning process keeps the plan,
and your tests and your logic stay yours. It writes no tests of its own.

## How it works

When you ask for a new page, a feature or a refactor, the agent goes through four
phases:

1. **Find the pattern.** It takes the page you name as the reference, or picks
   the nearest one and says so, and reads it top to bottom and left to right:
   the holders, the components in each, how each is written, how forms validate
   and errors are shown. Then it searches how the other pages reuse those pieces.
   Values come from your theme. Where your project disagrees with itself it
   decides by a written order and tells you what settled it, with the numbers.
2. **Plan.** One task per page, each carrying its checklist and what not to copy
   from the reference. It shows you the plan and waits for a yes.
3. **Implement.** One page at a time, from the checklist, in a fresh context.
4. **Verify.** A separate agent compares each page with the reference, region by
   region, and then all the pages together. Before its result counts, the check
   is proved to catch a difference planted on purpose.

A new page with nothing close enough to follow gets its shape agreed with you
first, in words, as a tree of your own components. It is drawn, with your
project's values, only if you ask to see it.

A small change to one page skips the plan. Checking code that is already written
is the last phase, after the first one where no checklist exists yet.

It works on its own, and it works inside another process: where
[superpowers](https://github.com/obra/superpowers) or another process has already
written a spec or plan, the phases add to it instead of running a second one.

The agent you already use does all the reading. There is no parser, no API key
and nothing to configure. The one thing the plugin runs is a short session hook
that prints which skills a job takes, and where to report a page that came out
wrong; it needs no Node and installs nothing.

## Installation

### Anthropic's directory

The plugin is listed in Anthropic's directory. Add it there from claude.ai,
Cowork or the desktop app; Claude Code then loads it as `ui-consistency@synced`,
with no marketplace to add.

### Claude Code

In a session:

```
/plugin marketplace add kamenkurtev/ui-consistency
/plugin install ui-consistency@kkurtev-plugins
```

From a terminal:

```
claude plugin marketplace add kamenkurtev/ui-consistency
claude plugin install ui-consistency@kkurtev-plugins
```

### Gemini CLI

```
gemini extensions install https://github.com/kamenkurtev/ui-consistency
```

### Codex

```
codex plugin marketplace add kamenkurtev/ui-consistency --ref release
codex plugin add ui-consistency@kkurtev-plugins
```

Reads `.codex-plugin/plugin.json`, which gives it the skills, and runs the
session hook from `hooks/hooks.json`.

Codex runs a plugin's hook only once you have trusted it. At the first start it
warns that a hook needs review: open `/hooks`, review the plugin's
`SessionStart` hook and trust it. From then on every session gets the order the
skills run in. A clean Codex session has started `finding-patterns` on *Add a
returns page like the orders page* before writing any page code.

### GitHub Copilot CLI

```
copilot plugin install kamenkurtev/ui-consistency
```

Reads `plugin.json` and loads the skills from `skills/` and the session hook
from `hooks/hooks.json`. This path has not been run end to end.

### Cursor

Reads `.cursor-plugin/plugin.json`. Install per Cursor's plugin instructions,
pointed at this repository.

### Anything else

Point your harness at `skills/` and `USING.md`. Nothing in them is
harness-specific. `USING.md` gives the words to hand a phase to an agent with.

## The skills

The agent picks them up on its own. You don't need to name them.

- **finding-patterns** — how pages of this kind are built here
- **adjusting** — a change to one region of one page, the way the others write it
- **planning** — one checkable task per page
- **implementing** — one page at a time, from the checklist
- **verifying** — a separate agent compares each page with the reference
- **design** — reads a design for the page, or agrees its shape with you in
  words; draws it only when you ask
- **values**, **conventions**, **decisions** — called by the others when a step
  needs them: your theme and scales, counting what your pages do, and the order
  that settles a choice
- **accessibility** — optional: measured against a standard only when you ask
  for it or your project states a requirement

## What a task gets

A **checklist**: your page's own structure turned into questions, in the order
the page is read. Shown here with roles; yours carries your own component names.

~~~~markdown
new form page against form page (all four render the same holder and a form)
— from <the page you named>, 4 members of 5 candidates in <your app>, read 2026-08-30

- [ ] page holder — <your holder>, as its own landmark — 4 of 4, 4 files
- [ ] title one level down, in the toolbar — 4 of 4, 4 files
- [ ] form — <your validation approach>, not its own — 4 of 4, 4 files
- [ ] field — label tied to it, error under it, through <your field> — 8 of 8
- [ ] submit — <your button>, full-width, in the content area — the majority,
      3 of 4 across 4 files
- [ ] request failure — <your shared error helper>, not a new message box —
      the shared piece, against the copy in <a page>
- [ ] colour and spacing through the theme; no literal, nothing off the base
- [ ] not copied from <the page you named>: <what only that page has>
~~~~

Every line carries **how**, not whether, and what settled it — so ticking one
means opening the page. An agent that did not write the page walks the checklist.

**Nothing is left behind.** The counts are true of the code as it was read, and
code moves on: a file of them would be a thing to review, keep in step between
branches, and find stale. The checklist belongs to the task and goes with it.

**Plans** — when no other process wrote one, and **never in your repository**.
Each task carries its own checklist, which is what makes it executable by
somebody who was not in the conversation. Planning ends in one of three ways,
and says which:

1. **The work stays in one session.** The plan lives there — or, if the work
   outlives the session, in a scratch file outside your working copy, deleted
   when the work is done.
2. **The work becomes a story for somebody else.** The plan is attached to the
   story, complete enough that a developer without the conversation or the
   checkout could implement it from the attachment alone.
3. **Another process is running.** The tasks go into its plan; no second
   document.

When the work is done, what you decided against the order is reported with the
result; the plan itself goes.

## Three things you can say to it

Most of the time you say nothing: where your project agrees with itself, the
agent takes the answer and moves on, and where it disagrees the agent decides by
a written order and tells you what settled it. Three sentences are worth knowing
anyway. Two of them outrank everything it counted, and the third shows you a
page before it exists.

**Point at a page.** A page you name beats any number of pages that disagree with
it — which is what you want on a codebase that has been through three eras.

> *Add a returns page like the orders one.*

Everything is then read from that page, and the counts only separate what repeats
across the rest from what belongs to it alone. Without it the agent picks the
nearest page itself, and says which one it picked and why.

It settles what the page **is** — which parts it has, in what order, how it
behaves — not whether to reach for something your project already shares. A page
worth pointing at is often an old one, written before the shared helper existed;
copying what it hand-writes would produce exactly the drift you installed this to
stop. So the shared piece wins there, and you are told: *the page you named
writes its own error box; the shared helper is used by 3 of 4 — I used the shared
helper.*

**Overrule a decision.** Where the agent reports something you disagree with, say
so once:

> *Submit buttons are full-width here from now on, even though most pages still
> write them auto — we are half way through changing it.*

That is an **override**, and it is worth having precisely because it contradicts
the count: the agent would otherwise follow the majority and keep writing the old
way, correctly and unhelpfully. It outranks everything below your request,
including every count. It is written down where your process already records
decisions — the spec, the plan, the design document — not into a file of this
plugin's own, and there it stands until somebody changes it. With no such
process it is reported with the result and nothing keeps it, so say it again
next time. Nothing invents one: if you did not say it, it is not there.

**Ask to see it.** Before any code is written, you can ask what a page will look
like:

> *Show me how the returns page will look.*

The agent draws it as one static page with your project's own spacing, type and
colours, each region labelled with the component that will fill it, and opens it
in your browser. Ask for two or three arrangements and it draws them on the same
page. It never draws unasked, and it never reads a value back out of a drawing:
the values stay your theme's.

## Philosophy

- **Your conventions, not ours.** No component name is built in. Every technology
  and every team names its own.
- **A page you name outranks a count**, and an override outranks that — above.
  Counts come with where they were found and in how many files, because four
  identical buttons in one file are one page's habit.
- **Before, not after.** An agent that reads the pattern first sets out to write
  the right page once, rather than fix it afterwards.
- **It decides, you are not interrogated.** A written order settles what a count
  alone cannot, and every decision is reported with what settled it. Three
  things wait on you: the plan, before any code; a tie whose answer changes code
  outside the task; and a new component the request did not name with its
  place, or code extracted into one, asked with what it touches. A request that
  says two things in one place, or leaves open what a page shows, holds up only
  that part until you answer.
- **Silence is never success.** Where it could not read something, it says so.

Read [docs/concept.md](docs/concept.md) for the reasoning.

## What it does not do

It is not a linter and not a CI gate — nothing fails a build. It has no opinion on
whether your design system is any good. It has one subject: *does this look and
behave like the rest of this project.*

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[code of conduct](CODE_OF_CONDUCT.md). A vulnerability is reported privately —
see [SECURITY.md](SECURITY.md).

## Updating

In Claude Code: `/plugin marketplace update kkurtev-plugins`. What each version
changed is in [RELEASE-NOTES.md](RELEASE-NOTES.md).

## License

MIT — see [LICENSE](LICENSE). Provided as is, without warranty of any kind.

The plugin collects, stores and sends no data — see [PRIVACY.md](PRIVACY.md).
