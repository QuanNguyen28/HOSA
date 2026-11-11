# Pull request rules

What happens before a PR is merged, in this order. Each step either edits the
input of the next or judges its output.

1. **`scripts/gate.sh`.** The checks of the skills, the manifests, the hook and
   private names, the version check, the proof that each check fires, plugin
   validate. Nothing below is worth doing on a red gate.
2. **Simplification review** — reuse, simplification, efficiency. First, because
   it is the only review that edits.
3. **`scripts/gate.sh` again**, if the simplification changed anything.
4. **Correctness review.** Scoped: say what the change touches and what it
   claims, then check those. Fix what it finds; a finding judged wrong gets one
   sentence of why.
5. **Security review.** Last, so it judges what actually ships.
6. **The documents**, per `uic-docs.md`: read against the change, and fix what is
   false together with its copies.
7. **The one fresh read**, if a skill changed
   (`.claude/skills/uic-writing/SKILL.md`, *After writing*), and its fixes.
8. **`scripts/gate.sh` again**, if anything above changed a file.
9. **Open the PR and merge it** — how is in `uic-git.md`.

## How the reviews are done

By reading the diff against each angle, one at a time, over named surfaces rather
than the whole tree — and the PR body says they were done that way. `/simplify`,
`/code-review`, `/security-review` or review agents are used when the owner asks
for them; several review agents in parallel have exhausted a session and
returned nothing.

## All three, every time

Not conditional on the size of the diff or on the change being "only prose". A
judgement that a review would find nothing is not evidence that it would: a
security pass over a scope already declared safe once found four reproducible
defects.

## Reproduce a finding, in both directions

A finding is a hypothesis.

- **Before fixing it**, confirm what the code does, not what the report says. A
  report is often right about the defect and wrong in its details.
- **Before dismissing it**, make sure the check that came back green actually
  exercises the defect. A test that does not fail against the unfixed code is
  not evidence — run it both ways.

## The PR body

The template is `.github/pull_request_template.md`; every section is filled.

- who produced the change — model, harness, plugins — and who read the whole
  diff: a person, for a contribution from outside; for the owner's own
  agent-made change, that it merges on the gate and the three reviews;
- that open and closed pull requests were searched, and how the change stays
  inside what `docs/concept.md` says this is not;
- the issue's acceptance criteria, ticked where met;
- each of the three reviews and what it found — "found nothing" is a result;
- which documents were read against the change, and what was found;
- where it was exercised, with a transcript when it changes how a harness
  loads the plugin;
- what was **not** validated.

A review nobody ran has no wording that fits here.
