<!--
BEFORE SUBMITTING: Read every word of this template, and AGENTS.md. Pull
requests that leave sections blank, carry several unrelated changes, or show no
real work behind them are closed without review.

Link the issue: `Closes #<number>`, and one `Closes` per issue — `Closes #6 and #19` only parses the first.
-->

## Who is submitting this pull request? (required)
<!-- We assume an agent wrote it — say which one and where it ran. A change
     reasoned out of documentation and a change grounded in real work are
     different evidence, and without this they look identical. -->

| Field | Value |
|-------|-------|
| Your model + version | |
| Harness + version | |
| All plugins installed | |
| Human partner who read the complete diff | |

## What problem are you trying to solve?
<!-- The run that went wrong: what was asked, what the agent did, what it
     should have done. "Improving" something is not a problem statement. -->

## What does this pull request change?
<!-- 1–3 sentences. What, not why — the why is above. -->

## Does it belong here?
<!-- Answer the change against `docs/concept.md`, *What this is not* — not the
     whole job, not a test suite, not a linter, not a design-system opinion,
     not a gate, not a program, not for sale — and against *What We Will Not
     Accept* in AGENTS.md. Which of these could a reader say this change makes
     it, and why it does not? -->

## What alternatives did you consider?
<!-- What else did you try, and why was it worse? None considered is a red
     flag; say so if it is true. -->

## Does this pull request contain multiple unrelated changes?
<!-- If yes: stop and split it. **One logical change.** A pull request carrying
     unrelated changes is split, not reviewed (`.claude/rules/uic-git.md`). -->

## Existing pull requests
- [ ] I searched open **and closed** pull requests and issues for the same
      problem or prior art
- Related: <!-- #n, or "none found" -->

<!-- Where a related one was closed: what is different this time. -->

## Acceptance criteria

Copy the issue's criteria and tick each one. A criterion this pull request cannot
meet is changed or dropped on the issue before the merge; the issue closes when
this merges.

## Environment tested

| Harness | Harness version | Model | Model version/ID | What was run |
|---------|-----------------|-------|------------------|--------------|
|         |                 |       |                  |              |

## Harness support (required if this changes how a harness loads the plugin)
<!-- The one session this project asks for: it proves the plugin loads, not how
     a skill behaves (AGENTS.md, *Skill Changes Come From Real Work*).
     A manifest, the hook, `USING.md`, `GEMINI.md`: attach a
     **transcript** of a clean session in that harness, in a project with pages
     already built, sending exactly

         Add a returns page like the orders page

     A working integration starts `finding-patterns` before any page code is
     written. `.claude/CLAUDE.md` says which harnesses have never been run end to end; a
     change to one of them is the first evidence it works, or it is not. -->

<details>
<summary>Clean-session transcript</summary>

```
paste the complete transcript here
```

</details>

## The real work behind it
- For a skill change: the page that came out wrong in real work — what was
  asked, what the agent did — or the defect in the text it fixes, and what the
  agent must now do differently. Described by role, never by name.
- A change of wording that leaves what the skill asks the same: say so.
- If a skill changed: what the one fresh read of the changed lines found, what
  was fixed and what was only named (`.claude/skills/uic-writing/SKILL.md`,
  *After writing*) — "nothing" is a result.

<!-- No test runs: a skill change is checked the next time the plugin is used
     for real work (AGENTS.md, *Skill Changes Come From Real Work*). -->

## Verification

- [ ] `scripts/gate.sh` passes
- [ ] A line under `## Unreleased` in `RELEASE-NOTES.md`, or nothing that ships changed (a release: `scripts/bump.sh`, and its own pull request)
- [ ] **A changed check fails against the unfixed version** — a plant in `scripts/test-checks.sh`, run both ways — or no check changed
- [ ] A change to the hook was run the way a harness runs it: `hooks/run-hook.cmd session-start`
- [ ] No name from a private repository in the diff — numbers survive, names do
      not (`.claude/rules/uic-docs.md`)

## Reviews — all three, every time

There is no "not applicable". State what each found; **"found nothing" is a
result** and belongs here.

- [ ] Simplification pass — what it changed
- [ ] Correctness review — what it found
- [ ] Security review — what it found

## Documents

Which of the documents `.claude/rules/uic-docs.md` lists you read against this
change, and what you found. **"Read, nothing false" is a result.**

## Human review
- [ ] A person read the complete diff before submission — not a summary of it.
      Required of every contribution from outside. The owner's own agent-made
      changes merge on the gate and the three reviews instead
      (`.claude/rules/uic-git.md`), and say so here.

<!--
STOP. A contribution from outside with the box above unticked is not submitted.

Closed without review:
- no evidence of a person or of real work behind it
- several unrelated changes
- a script or parser for analysis, or a technology's names in the skills
- a name from a private repository
- required sections blank or placeholder text
- a skill's behaviour changed with no real work behind it
-->
