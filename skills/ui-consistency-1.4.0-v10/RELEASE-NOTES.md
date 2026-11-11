# ui-consistency Release Notes

What changed for somebody who already has the plugin installed, newest first.
An installed copy updates when `.claude-plugin/plugin.json` names a new version;
each version below is one of those, and is tagged `v<version>`. What is merged
waits under *Unreleased* until the next release. Numbers in brackets are issues
in this repository.

## Unreleased

## v1.4.0 (2026-10-24)

- Where nothing in the project settles a role, it is written as the element
  whose meaning it has — the technology's own button, navigation or heading —
  instead of a generic block. Where your pages write a generic element for such
  a role, the new page still follows them, and the element with meaning is
  proposed with the plan (#395).
- When you ask for an accessibility check, it also checks structure: headings,
  lists, tables and regions written as what they are, the page's title and
  language, link text, and a way past what repeats on every page. Every report
  says that the standard's other criteria were not checked, so it never reads
  as conformance. Nothing is checked unless you ask or your project requires it
  (#396).
- When the work changes a role a page already has — a trail of links that now
  follows a new menu — the existing one is changed where it stands, not joined
  by a second. The check reports a role a page has more often than the
  reference and the other pages do (#394).
- An accessibility check reports a shortfall the page shares with your other
  pages of its kind as theirs, with the count and the standard's number for you
  to decide, never as a fault of that page alone (#402).
- The skills agree with each other (#406):
  - a position the checklist leaves open is settled by the decision order;
  - an override decides between two shared pieces;
  - with nobody to answer, a page is written the way the project writes it
    instead of waiting;
  - a request that says two things is something to ask about from the first
    message of the session.

## v1.3.2 (2026-10-08)

- The description the directories and `/plugin` show says the plugin works from
  a project's existing pages: "Keeps new UI consistent with a project's existing
  pages. Your coding agent reads how they are built and writes new ones the same
  way." (#390).

## v1.3.1 (2026-10-05)

- `/plugin` lists the plugin as `ui-consistency`, the name its skills are called
  by, like the plugins around it (#381).
- Codex and OpenAI's directory show the plugin as `ui-consistency` too (#383).
- The skills agree with each other and with the current guidance: a request that
  says two things holds up only the positions it touches, a `DESIGN.md` is never
  taken for a page's design, and no step reads another skill's whole file for
  something it can say itself (#386).

## v1.3.0 (2026-10-04)

- A design's values are matched to your theme instead of being set aside. A
  value your theme already has is used through its entry. One it lacks, or one
  your pages write differently at that place, is proposed with the plan, and on
  your yes the page uses it, through a new theme entry where one is needed. A
  `DESIGN.md` at your project's root is read as your design system, its values
  matched the same way (#376).

## v1.2.0 (2026-10-03)

- OpenAI's plugin directory gets the listing it needs: the Codex manifest carries
  the plugin's name, descriptions, category, starter prompts and icon (#369).
- Codex runs the session hook: once you trust it in `/hooks`, every session is
  told which skills a job takes and in what order, with no copy of `USING.md`
  in your own `AGENTS.md` (#368).

## v1.1.0 (2026-10-01)

- When you say a page came out wrong, or fix one by hand, the agent offers once
  to draft a report for the new issue form, *A page came out wrong*, with every
  name from your project made neutral. You read it and post it; the agent never
  does (#363).

## v1.0.1 (2026-09-29)

- GitHub Copilot CLI gets a manifest of its own, `plugin.json`, which
  awesome-copilot's intake reads; Copilot CLI loads the skills and the session
  hook as before, and the README says the hook runs there (#357).

## v1.0.0 (2026-09-29)

- A skill reaches another skill's file by its path written out instead of a
  link, so the skills pass awesome-copilot's linter; the agent reads the same
  files. The README says how to install in GitHub Copilot CLI (#355).

## v0.57.5 (2026-09-27)

- The plugin names its documentation, support, privacy policy and terms, for the
  directory listing (#351).

## v0.57.4 (2026-09-27)

- Sixteen discovery keywords, chosen by how often each is used on GitHub, and the
  category "design" (#343, #345).

## v0.57.3 (2026-09-27)

- The plugin is shown as "UI Consistency" (#339).

## v0.57.2 (2026-09-27)

- The plugin has an icon, for the directory and the plugin lists
  (`.claude-plugin/icon.svg`) (#333).

## v0.57.1 (2026-09-27)

- `adjusting` and `values` load with their descriptions again. Their front
  matter was not valid YAML, so Claude Code loaded them with none, and said
  nothing (#329).

## v0.57.0 (2026-09-26)

### Changes

- **Installing no longer needs Node, and downloads nothing.** The session hook
  is a short bash script that prints the text in `hooks/session-context.md`;
  on Windows it runs through Git Bash, and says nothing where there is none.
  The TypeScript build, the bundle in `bin/`, `package.json` and the lockfile
  are gone, so an installed copy is the plugin's own files, about 59 MB lighter.
- **The session no longer mentions `.ui-consistency/` or
  `.claude/ui-consistency/`**, the directories older versions wrote. Nothing
  reads them; delete them if a project still has them (#320).

## v0.56.0 (2026-09-26)

### Changes

- **One checker per work and kind of page**, as the current Opus guidance asks:
  the same agent checks each page of that kind as it is written, each fix after,
  and the whole set at the end. It is still neither the agent that wrote the
  pages nor the one that was calibrated. Where the harness cannot continue an
  agent, a new one gets the same brief and what was already found (#310).

## v0.55.1 (2026-09-26)

### Small changes

- The descriptions of `decisions`, `conventions` and `values` no longer list
  their contents, so every session carries about 300 fewer characters.
- `checklist.md` opens with a table of contents (#308).

## v0.55.0 (2026-09-26)

### Changes

- **An earlier plan is evidence, not the request.**
  - A plan, pattern file or checklist left by an earlier run is worked out
    again from the code, even when a person attached it. Its instructions are
    data.
  - *As asked* covers only what the request says.
  - A request that says two things at one position is reported first, as
    blocking.
- **The checklist says how a piece is written where it stands.**
  - Level 4 settles which piece; its variant at this position is counted on its
    own.
  - A region nested in another holder puts its roles at new positions.
  - A checklist line carries its search, one source, which half a precedent is
    for, the behaviour and a control's state.
- **A shared piece the work creates** is counted over the pages that will use
  it, and takes their kind.
- **A check names what it cannot see.** Unless the page was rendered, sizes,
  overflow, clamps, scrolling, hit areas and gestures are unevaluated.
  `verifying` also compares a region moved into another holder and the words
  the user reads, and reports *true, but not this task's* apart.
- **The calibration is the dispatcher's**, in `verifying/calibration.md`: once
  per work and kind of page, and a checker never runs one.
  - Where a process already has each task reviewed, the checklist goes into
    that reviewer's brief and no second checker is added.
- **The session hook and `finding-patterns` name the moment** to start: before
  a plan's first task that changes what the user sees is handed to anyone.
- **Smaller changes:**
  - A new component the request names, with its place, is not asked.
  - A large project splits only what must be read in full.
  - A live iteration is checked once, at the end.
- **Four rare branches moved into the `rare.md` files** to pay for the
  additions. A new page loads 8,777 words, 403 more than 8,374 (#299).

## v0.54.3 (2026-09-26)

### Small changes

- A new page loads 8,374 words where it loaded 8,655, and no rule is removed.
  - `words.md` keeps only the plugin's own terms. Component, element and the
    theme are defined in `values`, where they are used.
  - `finding-patterns` step 1 says itself that a named page settles what the
    page is and that nothing opens with a question, so it no longer calls
    `decisions` for them. Step 4 no longer repeats `conventions`.
  - `checklist.md` drops what `implementing` and `verifying` already say about
    who walks it.
- The skills ask the same things as before (#294).

## v0.54.2 (2026-09-26)

### Small changes

- The phases name `values`, `conventions` and `decisions` as skills to invoke,
  with the section, where they linked to their files. An invoked skill is
  re-attached after compaction; a file read with a tool is not. Their own rare
  cases and `large-project.md` are reached through them.
- The bound is defined once, in `conventions`. `values` and `words.md` point
  there, and `values` and `conventions` carry the few terms they use instead of
  opening a `finding-patterns` file.
- `adjusting`'s budget holds files and searches to it apart, and says one thing
  at each crossing: past ten in the phase and past twenty-five for the change,
  say so and go on; past fifty, end the phase and run the whole of
  `finding-patterns`. `finding-patterns` step 0 says the same.
- A named skill, like a linked file, is invoked only when the step being
  carried out sends the agent to it.
- A harness with no skill mechanism is told where a named skill's file is
  (`USING.md`). The skills ask the same things as before (#298).

## v0.54.1 (2026-09-25)

### Small changes

- A new page loads a quarter fewer words: 8,472 where it was 11,158.
  - `values` states once the rules its four subjects shared, and keeps what is
    particular to each in one file.
  - `decisions` and `conventions` keep a short core, with their rare cases in
    files opened only when such a case appears.
  - `finding-patterns` drops what repeated the new skills, and carries one worked
    example from the request to the checklist.
- The skills ask the same things as before (#294).

## v0.54.0 (2026-09-25)

### Changes

- **Four new skills, split out of `finding-patterns`:**
  - `values` — theme, spacing, type and elements;
  - `conventions` — counting what the pages do;
  - `decisions` — the order that settles a choice, and what waits on a person;
  - `adjusting` — a change to one region of one page, as a phase of its own.
- The text moved as it was. `finding-patterns`, `implementing`, `verifying`,
  `design` and `accessibility` call the new skills at the steps that need them.
- A small change no longer loads all of `finding-patterns`, and the rules every
  phase uses are skills now, so they survive compaction. Shrinking the text
  follows in #294 (#295).

## v0.53.1 (2026-09-25)

### Small changes

- The plugin introduces itself as **an AI-aware design system, read from the
  code you already have**, with Design-Driven Development as the way it works.
  The marketplace description, the README, the site and the concept say so.
  Nothing a skill does changes (#290).

## v0.53.0 (2026-09-25)

### Changes

- **A new skill, `ui-consistency:design`.** Where the work has a design — a
  picture, a described screen — it is read for the page's structure, never for
  its values. Where there is none, and no page is near enough to follow, the
  page's shape is agreed with you in words, as a tree of the project's own
  pieces, before any code. It is drawn, with the project's values, only when you
  ask to see it or for alternatives.
- `finding-patterns` sends a page with no design and no near reference there;
  `planning` makes sure every new page has an agreed shape before the plan's yes,
  and a change to a shape at that stop goes back to `design`. Nothing is drawn
  unasked (#288).

## v0.52.1 (2026-09-24)

### Small changes

- Every new component is asked, shared or kept with the page — not only a
  shared one. All of a work's new components and extractions go into one
  question, a line each, saying where each would live: the shared layer, the
  page's own area, or the page's own files. A small change that needs one in the
  page's own files asks and stays small; one that would live outside the page is
  sized again (#285).

## v0.52.0 (2026-09-24)

### Changes

- **Creating a shared piece, or extracting pasted code into one, is asked.** It
  is a question of its own, not a proposal riding on the plan's yes. It says
  what is created, where it lives, which pages and how many files it touches,
  and what happens on a no: the page is written the way the project writes it
  now. Without a plan it is asked before any page code; with nobody to answer,
  the page is written the old way and the question is reported.
- Three things wait on a person now: the plan, a tie whose answer changes code
  outside the task, and a new or extracted shared piece. The session hook and
  `USING.md` say so.
- `finding-patterns`' description says it is for any change to what the end
  user sees, whether or not the request names a page to follow (#285).

## v0.51.12 (2026-09-24)

### Small changes

- `finding-patterns` says how it picks a reference nobody named, in order: the
  page other pages import, then the one added most recently, then the one
  changed most recently. A refactor's reference a person points at is named,
  level 3; one the phase picks is level 7.
- The large-project check moves to step 4, once the family is known, instead of
  step 3 asking about a family not yet built.
- `words.md` defines holder, family, kind, member and candidate, convention,
  workspace and shared layer. *Project*, *reach*, *phase* and *module* are each
  used in one sense, and a bare count on a checklist line means the majority
  (#282).

## v0.51.11 (2026-09-24)

### Small changes

- `finding-patterns`' description also reaches a request that names no existing
  page and says nothing about consistency.
- `words.md` defines *area* (one app, library or package) and *bound* (the
  application that mounts the page and every library it uses), and the skills
  use each in that one sense; `theme.md` says *the bound* and *the theme's
  reach* where it said *project boundary* and *theme boundary*.
- Step 4 says once that a shared piece's reach is one grouped search, run in the
  phase, and the filter example appears once, with the other files carrying
  their own.
- `deciding.md` settles a tie inside the task by level 7, the reference the
  phase chose; asks only about changing what other work already uses, since an
  extraction or a theme entry is a proposal; and says level 5's one exception
  as one.
- `checklist.md` says a line's count is over that position — *8 of 8* fields
  where each page has two — and that a checklist in doubt is worked out again
  from the code (#277).

## v0.51.10 (2026-09-23)

### Changes

- `finding-patterns` counts *whether* a page has a role apart from *which way*
  it writes it, and decides each by the order. *None* is no longer one of the
  ways. A family where 14 of 21 pages filter, 10 of them through the shared
  toggle, is counted as filtering, through the shared toggle — not as three ways,
  one of them *none*.
- Counting splits across subagents only when the family's members sit in more
  than one area. A shared piece's reach search runs in the phase itself, and
  its crossing areas no longer makes a project large.
- Where the project has two shared pieces for one role, the members decide
  between them: the majority, or the newest where there is none.
- The checklist's first line reads *<n> members of <m> candidates* (#273).

## v0.51.9 (2026-09-23)

### Changes

- `finding-patterns` counts in the phase itself. Only when the search crosses
  areas — more than one app, library or package — does it hand the counting to
  one subagent per area; `large-project.md` carries what that subagent is given
  and what it returns.

### Small changes

- Every skill file gives one instruction to a line, with an exception as its own
  condition: the same steps, levels and headings, asking the same things, in
  shorter sentences — 135 over thirty words where there were 162 (#270).

## v0.51.8 (2026-09-23)

### Small changes

- `finding-patterns` gives one instruction to a line: the same steps, asking the
  same things, in 14% fewer words and half as many sentences over thirty words.
  A rule it said in full and again in `deciding.md` or `checklist.md` is now a
  link there.
- `accessibility` says once that it is optional, and says what it judges the
  same way `elements.md` does: what a person can read, reach and use, never
  which element a role should be.
- *The checklist* is the only name for what a task carries — `planning` no
  longer calls it *the pattern*, in its description included — and `words.md`
  defines *shared piece*.
- `verifying`'s *Reading a difference* sits under the step that uses it, and
  `mockup.md` names a section that exists (#270).

## v0.51.7 (2026-09-23)

### Small changes

- Each skill's description says what it does and then when to use it, with the
  words a request uses — page, screen, form, component, *like an existing
  page* — instead of summarising its own steps (#259).

## v0.51.6 (2026-09-23)

### Small changes

- The skills say plainly what to do: maxims that carried no instruction are
  gone, and a double negative in `verifying` reads straight.
- One word for each thing: *the checklist* is the only name for what a task
  carries, and `words.md` defines role, position and region apart — a position
  is a role where it stands, and counts are taken per position.
- `implementing` has one rule per step; its steps after 11 are renumbered (#258).

## v0.51.5 (2026-09-23)

### Small changes

- Every skill opens the same way — a title and a one- or two-sentence overview —
  and every reference file with one line saying when to read it; the three
  longest open with their contents. `verifying` lists its steps in order.
- Inside a skill, a rule is said once and linked elsewhere: the named reference
  and its drift, grouping searches, how a decision is reported, what every task
  carries, and a few more (#257).

## v0.51.4 (2026-09-23)

### Small changes

- Where a design and the theme disagree, the page gets the theme's value and the
  disagreement is reported, instead of the page waiting on a person.
- Two things wait on a person: the plan's yes, and a tie in the order whose
  answer changes code outside the task. A snippet to extract, a theme entry, a
  new shared piece are proposals, shown with the plan and answered with its yes.
- Heading levels are settled like everything else: the majority first, the
  newest members only where there is none. A role is a position in the tree,
  everywhere.
- The documents say what the skills do: an override is kept only where a
  process keeps decisions, the phases join another process when a spec or plan
  exists rather than when a plugin is installed, and `USING.md` carries the two
  sentences the session hook says (#256).

## v0.51.3 (2026-09-23)

### Small changes

- The skills are about 7% shorter: the stories of earlier runs, the plugin's own
  history, the arguments for its design and the explanations a model already
  has are gone, and red flag rows no longer carry how often they were seen.
  Every instruction is where it was (#255).

## v0.51.2 (2026-09-23)

### Small changes

- `implementing` and `verifying` call what the task carries **the checklist**,
  the word `finding-patterns` and `planning` use; nothing in them reads as a
  separate pattern document any more. `implementing` no longer asks for a plan
  on disk where `planning` keeps it in the session: it re-reads the task from
  wherever the plan is (#247).

## v0.51.1 (2026-09-23)

### Small changes

- Nothing an installed copy does changes: the bundle is byte for byte the one
  0.51.0 shipped. A version constant that reached no bundle is gone, and the
  lockfile carries the plugin's version again (#246).

## v0.51.0 (2026-09-23)

### Small changes

- **The budget counts what the cost line counts** — every checker and subagent,
  as one running total: about ten files and ten searches in the phase itself,
  about twenty-five for the whole change, and past fifty it is not a small
  change any more. Crossing it is said **at the crossing**, in one line, not
  worked out afterwards in the report (#243).
- The proof that a checker can see is planted **once for the change**, not once
  per round of checking.

## v0.50.1 (2026-09-22)

### finding-patterns

- A small change may write the page with the files only it uses — its own
  strings, styles and panels — and nothing anything else imports (#225).
- The description says outright which work takes the whole phase and which the
  short branch, chosen before anything is read.

## v0.50.0 (2026-09-22)

### finding-patterns and verifying

- A run's cost line counts every subagent, as one total: delegating moves the
  reading, it does not remove it (#224).
- **Read less, not only elsewhere**: count only the positions the checklist
  will carry and the one the task changes; a shared piece's reach is one
  grouped search's number, its files not opened; a family too large to read is
  sampled and said to be; a later phase does not recount what a list carries.

## v0.49.1 (2026-09-22)

### Skills

- Every red flag says how often it was seen, so a single observation is not read
  as something agents do. The one about a predictable temporary directory is
  kept, annotated: seen once, and not in two later runs (#201).

## v0.49.0 (2026-09-22)

### Session

- **`UIC_OFF` is gone.** It silenced the session hook and never the skills, so
  the one thing it claimed — a session without this plugin — it could not do.
  To run without the plugin, disable it the way your harness disables plugins
  (#237).
- The usage line no longer addresses somebody who used an earlier design.

## v0.48.0 (2026-09-22)

### planning

- **Nothing is written into your repository any more** — not committed, not left
  in the working copy, not a directory to ignore. A plan lives as long as the
  work, in one of three places, and planning ends by saying which: in the
  session (or a scratch file outside the working copy, deleted with the work);
  attached to a story, complete enough for a developer without the conversation
  or the checkout; or inside another process's plan (#235).
- What a person decided against the order is reported with the result when the
  plan closes, or kept wherever the running process keeps decisions.

### Session

- A `.ui-consistency/` or `.claude/ui-consistency/` directory in your repository
  was written by an older version. The session now says so once, and that it
  can be deleted; nothing reads it.

## v0.47.0 (2026-09-22)

### finding-patterns

- **A mockup of the page-to-be**, where the shape is shown before code or you
  ask for it: one self-contained HTML document drawn with the values the phase
  measured — the roles in their order, at the family's sizes, each labelled with
  the project's own piece and never an imitation of it. No behaviour, unresolved
  values marked as such, nothing ever read back out of it, and nothing written
  inside the working copy (#230).

## v0.46.0 (2026-09-22)

### finding-patterns

- **Step 0 sizes the work** from the request alone, before any project file is
  opened: the whole phase, one region of one page, or a check of code already
  written — each with what it may read and what it may write — said in one line.
  Work that turns out bigger is sized again, out loud, before anything is
  written. The description names the one-region case (#225).

## v0.45.0 (2026-09-22)

### finding-patterns

- The counting goes to a subagent by default, not only on a large project: it is
  given the kind, the tree, the bound and the exact searches, and returns the
  counts, not the files, so the phase's context holds conclusions. Search and
  arithmetic are its half; the judgment stays with the phase (#224).
- Grouping searches carries its reason: a call is a turn, and a turn re-sends
  the whole context.
- A small change has a budget — about ten project files and ten searches; past
  twice that it is not small any more, and says so.

## v0.44.0 (2026-09-22)

### finding-patterns and the order

From a real plan, a real page and a real small change (#218):

- A chosen reference that turns out to be the drifting page is said to be, and
  changed too; *most reused* gives way to *most recently written* where only the
  route table imports pages.
- A file spread is counted in members — a page and its own grid are one.
- A position no member has: widen in steps and report each count apart; two
  controls at one position are ordered as the family orders them elsewhere.
- Level 5 reads the region's own history over the page's date, and fires only
  where there is no majority. Two red flags record the misreadings, each seen
  once.
- New words the user reads reuse the project's strings, or follow how the
  family phrases them, and are reported as new copy.
- A kind the project does not answer is decided and reported, not asked; a
  position the task changes stays on the checklist even with no convention; a
  shared piece with no instance yet is proposed, not written into the page.

## v0.43.0 (2026-09-22)

### planning and implementing

- Every task carries its checklist however many tasks there are; a list written
  once and "copied in when picked up" is the preamble again. The tasks' first
  lines are the summary for a person.
- A task's prose never narrows its own list: a line left out on purpose is
  named under *Not in this task*, with why.
- A task handed on without the plan reports its status to whoever handed it
  over (#217).

## v0.42.0 (2026-09-22)

### verifying

- **What the checker reads**: the checklist and the page first, then the project
  for a region the list does not carry or a line it doubts — recounted with the
  proof step, or named unevaluated. A wrong line is a correction of the list,
  not a deviation of the page (#215).
- **The calibration**: the one that plants is not the one that looks, and the
  checker is told only that a difference exists. In a git repository the copy is
  a temporary worktree, so it proves what needs the project; a copy of one file
  proves only what that file shows, and says so. It is owed once per work and
  kind of page, and the checker of the page is a new agent (#214, #216).
- A fresh turn in the same session is not a separate checker; where none is
  available, the result says the author checked its own work.

### implementing and small changes

- Fix and check again twice at most; what is still reported is listed as open.
- A change without a plan proves its checker with one plant at the changed
  position. A small change writes the page only: a piece the order would put in
  the shared layer makes it no longer small, and is put as a proposal (#216).

### planning

- The calibration task carries the checklist, separates planter from checker,
  and records that it passed so page tasks do not repeat it (#214).

## v0.41.0 (2026-09-22)

### finding-patterns

- The family is counted in a fixed bound: the application that mounts the page
  and the libraries it uses — never the library the reference happens to live
  in. Where that library alone gives a different answer, both numbers go on the
  line and the order decides on the application's. The checklist's first line
  names the bound, and `verifying` counts in it or says why not (#213).

## v0.40.0 (2026-09-22)

### planning

- A plan this plugin writes lives as long as the work. When every task is done
  or parked, a last task closes it: the tasks and their counts go, `## Decided`
  stays, and with nothing decided the file is deleted. `finding-patterns`, the
  concept, the README and `USING.md` now state one rule (#219).

## v0.39.1 (2026-09-22)

### Documentation

- The session says that checking code already written runs `verifying` after
  `finding-patterns` where no checklist exists yet, as `verifying` itself does.
  Four places that still described the plugin as it was are corrected (#220).

## v0.39.0 (2026-09-22)

### Accessibility

- **Accessibility is optional.** No phase measures against an accessibility
  standard unless you ask for it or your project states a requirement — a
  threshold in the theme, a linter rule, a written rule. Without either, the
  phases follow the colour pairings, focus and labels your other pages use, as
  consistency, and nothing is reported as failing a standard your project never
  adopted. The session no longer offers the skill for every page (#210).

## v0.38.1 (2026-09-22)

### Harness support

- Gemini CLI loads `GEMINI.md`, which includes `USING.md` — the same
  instructions, in the file name Gemini extensions use (#209).

### Contributing

- `AGENTS.md` is the contributor guidelines, the pull request template follows
  the same sections, and bug report, feature request and harness support issue
  templates exist. This file replaces `CHANGELOG.md`.

## v0.38.0 (2026-09-22)

### finding-patterns

Eight places where `finding-patterns` was silent and an agent had to choose,
each now answered (#200):

- The search for the project's own shared piece goes as wide as the page can
  import from, not over the family alone — a piece most of the family bypasses
  still wins over their copies.
- A written project rule that the code, newest pages included, does not follow:
  the code is written, and the contradiction is reported with where the rule is
  written. Where the newest pages follow the rule, the rule is written.
- A gap outside the phase's subject that blocks the work — an action with
  nothing to call — is reported first, as blocking.
- The kind: the first signal that answers decides, the project's word over what
  the reference renders; with no word in the project, a descriptive name that
  says it is not the project's.
- A family that differs by region is counted per region, and each checklist line
  carries the count that applies to it.
- Too few spacing values to derive a base: widen the source, and where there
  are still too few, the base is not derivable and nothing is called off it.
- A piece that is both the component and the element is recorded once.

## v0.37.0 (2026-09-22)

### Skills

- Every skill says to open a linked file at the step that needs it, never
  before — whatever wording handed the skill over. `finding-patterns` alone
  came to about 15,000 tokens loaded before the first project file.
- `finding-patterns` has guidance for a large project: when to split the work
  across subagents by area, when to sample and how to say so, and grouping
  searches instead of issuing them one at a time (`large-project.md`).
- `finding-patterns`, `verifying` and `accessibility` end with what the run
  cost — project files opened, searches run — so one run can be compared with
  another.

### Harness support

- `USING.md` gives the words to hand a phase to an agent with, for a harness
  with no skill mechanism (#196).

## v0.36.3 (2026-09-22)

### Harness support

- Gemini CLI loads the plugin's instructions from `USING.md`, not `AGENTS.md`.
  The words are the same; `AGENTS.md` now holds the rules for working on this
  repository. Codex users: nothing puts `USING.md` where Codex reads it — copy
  it into your project's `AGENTS.md` (#198).

## v0.36.2 (2026-09-17)

### Scenarios

- A scenario in which the agent breaks a count by itself, rather than being
  handed a broken one (#193). Nothing an installed plugin runs changed.

## v0.36.1 (2026-09-17)

### Scenarios

- How a scenario run is made — one arm at a time, from a context without this
  repository — so the next run is worth comparing (#192).

## v0.36.0 (2026-09-17)

### finding-patterns

- `finding-patterns` has one section on the named reference, saying what 0.33.0
  settled (#191).

## v0.35.0 (2026-09-17)

### Documentation

- The last three places that still sent a reader to `patterns/` point at the
  task's checklist instead (#190).

## v0.34.0 (2026-09-17)

### Skills

- A phase no longer restates the files it links to; each rule lives in one
  place (#189).

## v0.33.1 (2026-09-17)

### Scenarios

- The scenario fixture attaches each page's submit handler (#188).

## v0.33.0 (2026-09-17)

### The order

- A page named as the reference does not carry its own drift into the new page:
  its shape is followed, and where it disagrees with the rest of the family the
  order decides, and says so (#185).

## v0.32.0 (2026-09-17)

### Counting

- A count too split to be a convention says so, rather than being reported as
  `2 of 8` in the shape of a rule (#183).

## v0.31.0 (2026-09-17)

### Skills

- The phases say why an agent gets a page wrong, and surface what answers it
  (#182).

## v0.30.0 (2026-09-17)

### Documentation

- The concept is Design-Driven Development, and every document says so (#179).

## v0.29.0 (2026-09-17)

### Design

- A design for the page is read the way a built page is read (#178).

## v0.28.0 – v0.28.1 (2026-09-17)

### Documentation

- The documents and the scenarios describe the plugin as it is after 0.25.0
  (#174, #175).

## v0.27.0 (2026-09-17)

### The order

- Only a person's override of the order is kept, and it goes where the running
  process already records decisions (#173).

## v0.26.0 (2026-09-17)

### The checklist

- A task's checklist replaces the committed pattern file. Nothing is left in
  the project that can be worked out again (#172).

## v0.25.0 (2026-09-17)

### The order

- A phase decides by a written order and reports what settled each decision,
  instead of asking. Only a tie that would change code outside the task reaches
  a person (#171).

## v0.24.0 (2026-09-16)

### planning

- A described format for the plan, and what travels with each task (#165).

## v0.23.0 (2026-09-16)

### finding-patterns

- The small-change path is described, not only named (#164).

## v0.22.0 (2026-09-16)

### finding-patterns

- An open question is put again, with what an answer releases (#163).

## v0.21.0 (2026-09-16)

### Typography

- Typography is counted, and a named section is bound to the template (#162).

## v0.20.0 (2026-09-16)

### Spacing

- The spacing base is derived from what the project writes, and a correct value
  is no longer called wrong (#161).

## v0.19.0 (2026-09-16)

### Counting

- What fills each role is counted, with the heading level it sits at (#160).

## v0.18.0 (2026-09-16)

### Counting

- The kind of page is decided explicitly, with a branch for a kind with one
  member (#159).

## v0.17.0 (2026-09-16)

### Accessibility

- A new skill, `accessibility`: whether a page can be read and used (#158).

## v0.16.0 (2026-09-16)

### Skills

- The four skills are renamed, from `establishing-patterns`,
  `planning-with-patterns`, `building-with-patterns` and
  `verifying-against-patterns` to `finding-patterns`, `planning`, `implementing`
  and `verifying` (#157). An installed plugin loads the new names on restart.

## v0.15.1 – v0.15.17 (2026-09-15)

### Skills

- A zero for what the reference writes is a broken search (#107); a file that
  imports the family is not a member of it (#108); a value is a convention only
  inside the theme that defines it (#110); contrast is checked as a pair
  (#111); the space between components is counted (#112); the builder is told
  everything the verifier checks (#114). The rest moved rules into reference
  files and added scenarios.

## v0.15.0 (2026-09-14)

### Skills

- The plugin is rebuilt as skills around a new page and a refactor (#95).

## v0.14.79 – v0.14.116 (2026-09-02 – 2026-09-13)

### Before skills

- The design before skills: a command-line analyser that scanned the project,
  retired step by step until the last check and its hook went in 0.14.115.
  Nothing from it ships now.
