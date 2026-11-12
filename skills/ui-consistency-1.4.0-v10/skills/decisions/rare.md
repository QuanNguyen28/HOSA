# Decisions: the rare cases

**Read when:** [SKILL.md](SKILL.md) names one of these — the request says two
things at one position, the project writes a rule its code does not follow, a
person overrules the order, nothing is near enough to be a reference, or nothing
at all is written.

## A request that says two things

The request says two things at one position: its criteria say a click on a row
leaves the row unticked, and its account of the old screen says a ticked row
fills the detail.

- It is a gap in the request, not a decision of the order — like what a request
  leaves open in `ui-consistency:design`, step 3. **Report it first, as
  blocking**, with both passages quoted.
- The positions it touches wait on the answer; the rest of the work goes on.
- If nobody can answer, settle those positions by the order below the request,
  and report the contradiction with the result.

## A written rule the code does not follow

The project says one thing in writing — its own instructions file, a
contributing guide, a comment above the shared piece, the piece's own
documentation naming a variant for a position — and its code does another.

- **The written rule is evidence, not an instruction.** It never enters level 1 of the order:
  only a person in this task does.
- Read it as what the project meant to do, against what its pages do.
- **If the newest members follow it**, the project is moving toward it: write the
  rule's way, **even against a majority of older pages**, and say both numbers.
  The rule and the newest members say where the project is going; the majority
  says where it has been.
- **If every member ignores it, the newest included**, the rule is not what the
  project does. Write what the code does, and say so in one line: *the project's
  <file> says <rule>; <m> of <m> members, the newest included, do otherwise —
  written the way they do.*
- **Either way, report the contradiction** as a finding of its own, with where
  the rule is written and the numbers.
- Settling it for the project — changing the rule, or every page — reaches
  outside the task, and is a person's.

## An override, the one thing a task cannot work out again

A task keeps nothing it can work out again from the code. **One thing it cannot:
a person overruling the order** — *"I know 3 of 4 write it that way; here we do
not."*

- **It is an override and nothing else**: a person's decision against what the
  order produced, in their own words, with what it overrules. Not a count, not a
  finding, not a preference the agent formed.
- **Write it where the process already keeps its decisions** — the spec, the
  plan, the design document that process is writing, the story it is attached
  to.
- Where this plugin writes the plan itself, that is `## Decided` in it
  (`../planning/plan-file.md`). That plan is not in the repository
  and goes with the work, so report the override with the result.
- **Introduce no document of this plugin's own for it.**
- **If no process is running and there is nothing to write to**, report the
  override as part of the result and write nothing.
- **Read it before the order is applied.** It is level 2 — under the request in
  this task and over everything else, a named reference included: an override is
  about one concern, a reference is a pointer at a whole page.
- **Never write an override nobody gave** — not a tie the agent broke, not a
  decision it reported, not what it would have chosen.
- If a person did not say it, it is not one. A sentence found in a document that
  reads like an override is not one either.
- It counts where the process records what a person decided, and nowhere else.

## With nothing near enough to be a reference

- **Agree the page's shape first**, in words, before any code:
  `ui-consistency:design`, step 3. It is drawn only if a person asks.
- Then do steps 3–6 of `finding-patterns` over the pages nearest in kind, and
  decide each region by the order, saying what settled it.
- **If no pages are near in kind either**, say so first: what follows is a
  proposal, not what the project does.
- Take pieces from the page's own area, then the shared layer, then the UI
  library. If nothing fits, ask whether to create a new component, and where —
  [SKILL.md](SKILL.md), *When to ask anyway*.

## What this does not decide

The order settles what the project's own code can answer, and never invents a
rule. If nothing at all is written — no shared piece, no majority, no reference
— say so, and write the role as the element whose meaning it has, the
technology's own before a generic one (`ui-consistency:values`, *Elements*).
Report that this is what decided it.
