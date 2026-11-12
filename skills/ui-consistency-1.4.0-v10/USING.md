# ui-consistency

**Design-Driven Development** for an agent writing UI: what the end user sees
drives the code, so a page comes out consistent and right while it is being
written rather than corrected afterwards. The right component written the way the
other pages write it, the project's own validation and error handling, values
from the theme. For any UI technology, including plain HTML and CSS.

Design first, and the design is read wherever it lives: a design for the page
where there is one, the theme and its tokens and a `DESIGN.md` where there is
one, otherwise the pages already built.

## Which skills a job takes

For anything the end user will see, these join the phases of whatever process is
already running, and run the phases themselves when none is. Use them without
being asked.

| The job | Skills, in order |
| --- | --- |
| a new page or feature | `ui-consistency:finding-patterns` → `ui-consistency:planning` → `ui-consistency:implementing` → `ui-consistency:verifying` |
| a refactor across pages | the same four |
| a small change to one page | `ui-consistency:adjusting` → implementing → verifying. The check is never the part that gets dropped. |
| checking code already written | verifying — after finding-patterns where no checklist exists yet |
| a design for the page, a new page with no page near enough to follow, or a wish to see a page before it is built | `ui-consistency:design`, on its own or from finding-patterns and planning. It agrees the shape in words, and draws it only when asked. |
| a step that needs the project's values, a count of what its pages do, or a decision between them | `ui-consistency:values`, `ui-consistency:conventions`, `ui-consistency:decisions` — reached from the phases; `values` also when somebody asks what the project's theme or scale is |
| measuring against an accessibility standard — only when asked for, or when the project states a requirement | `ui-consistency:accessibility`, on its own or from any phase |

If a process running this work has a spec or plan, add to it, and run
finding-patterns before its first task that changes what the user sees is
handed to anyone, whichever process wrote it. Decide by the order the skills
carry and report what settled each decision. Ask only about a request that says
two things or leaves open what the page must show; a tie whose change reaches
outside the task; and a component the request did not name with its place, or
code extracted into one.

- **finding-patterns** — reads the reference page top to bottom and left to
  right, searches what the other pages reuse and how, takes values from the
  theme, and writes the task's checklist. A named reference settles what the page
  is, not whether to use a piece the project shares.
- **adjusting** — a change to one region of one page: reads that one position
  across the family, skips the rest deliberately, and says so.
- **planning** — one task per page, each carrying its checklist, what not to
  copy, and a check by a separate agent; stops for a yes.
- **implementing** — one page per task in a fresh context, from the checklist.
- **verifying** — a separate agent compares each page with the reference region
  by region, with a check first proved to catch a planted difference.
- **design** — reads the design for a page where there is one; where there is
  none and no page is near enough to follow, agrees the page's shape in words, as
  a tree of the project's own pieces. Matches a design's values to the theme,
  and proposes a new entry for one the theme lacks. Draws a page only when
  asked, with the project's values, and never reads a value back out of its own
  drawing.
- **values**, **conventions**, **decisions** — what the phases call when a step
  needs them: the project's theme, spacing, type and elements; how to count what
  its pages do and tell a convention from a habit; and the order that settles a
  choice, with the three things that wait on a person.
- **accessibility** — optional: contrast, focus, reach without a mouse, a field
  and its label, text alternatives, target size and structure, each reported
  separately, measured against a standard only when somebody asks for it or the
  project states a requirement. Without either, the phases follow what the
  family already does, and nothing is reported as failing a standard.

If your harness has no skill mechanism, hand a phase to the agent in these
words, with the path filled in:

> Read and follow `<path to the plugin>/skills/<skill>/SKILL.md`. Open a file it
> links or gives the path of, or a skill it names as `ui-consistency:<name>` —
> that is `<path to the plugin>/skills/<name>/SKILL.md` — only when a step you
> are carrying out sends you to it. A path it gives starts from
> `<path to the plugin>/skills/<skill>/`.

Not *"and the files it links"*: that loads every linked file before the first
file of the project is opened.

## What it leaves in the repository

Nothing. A plan, when no other process wrote one, lives as long as the work and
never in the repository. Planning ends in one of three ways, and says which:

1. **The work stays in one context.** The plan lives in the session — or, if the
   work outlives it, in a scratch file outside the working copy, deleted when the
   work is done.
2. **The work becomes a story for somebody else.** The plan is attached to the
   story, complete enough that a developer who was not in the conversation, and
   does not have the checkout, implements it from the attachment alone.
3. **Another process is running.** The tasks go into its plan; no second
   document.

Each task carries its own checklist: the page's tree turned into questions, in
the order the page is read, with what settled each. What was counted is evidence
for the decisions in a task, reported with them, and not kept: code moves on,
and a count nobody notices has gone stale is worse than no count.

Nothing has to be configured. Everything is read from the project, and no
component name is assumed — every technology and every team names its own.

## When a page came out wrong

If the person says a page came out wrong, or fixes one by hand, offer once to
draft a report for the form at
https://github.com/kamenkurtev/ui-consistency/issues/new?template=a_page_came_out_wrong.yml.

- Put in what was asked, what was decided and what settled it, and what came out
  wrong beside what the other pages do.
- Rename every name from the project — component, file, path, route — to a
  neutral one of the same shape.
- Show the draft. The person reads it and posts it; never post it yourself.
