# Contributing

## The terms a contribution arrives under

The project is MIT-licensed (`LICENSE`). **Anything you submit — a pull request,
a patch, text in an issue meant to be used — is offered under the same licence**,
and you are saying you have the right to offer it on those terms. No separate
agreement is signed.

Conduct is `CODE_OF_CONDUCT.md`. A vulnerability is reported privately, as
`SECURITY.md` says — never in a public issue.

## Setup

```sh
scripts/gate.sh
```

Nothing to install: the gate is bash and perl, which come with git. It is the
whole bar — the checks of the skills, the manifests, the hook and private names,
the version check, the proof that each check fires, plugin validate. The same
script runs on every pull request (`.github/workflows/gate.yml`).

To work on the plugin while you use it, add your clone as the marketplace —
`claude plugin marketplace add <path to your clone>` — and every change applies
at the next session.

The plugin is Markdown — `skills/`. A change to how the agent behaves is a
change to a skill, not to `hooks/`, which holds only the session hook.

## Things that will bite a first contribution

**A change that ships adds a line under `## Unreleased` in `RELEASE-NOTES.md`**,
saying what somebody who installed the plugin will notice. A branch touching
`hooks/`, `skills/` or a manifest with nothing there fails the gate. Leave the
version alone: the owner cuts releases (`.claude/rules/uic-git.md`, *Versions*).

**A test that passes is not evidence.** A fixture written by whoever wrote the
rule encodes the same assumption as the rule. So:

- a fix to a check comes with a plant in `scripts/test-checks.sh` that **fails
  against the unfixed check** — run it both ways;
- a change to a skill comes from **real work** — a page built with the plugin
  that came out wrong — and is checked by feedback the next time the plugin is
  used, not in a test run. Its issue closes on the merge;
- a change to how a harness loads the plugin is run with the **shipped
  artifact**, installed, not from the clone (`AGENTS.md`, *New Harness
  Support*).

**Measurements keep their numbers and lose their names.** If you record what a
run on a private codebase found, rename every project-specific identifier to a
neutral one of the same shape first (`OrdersGrid`, `app-orders-grid`).
`scripts/check-private-names.sh` checks against a list you keep outside the
repository — `UIC_PRIVATE_NAMES` or `~/.config/uic/private-names.txt`. The rule
is `.claude/rules/uic-docs.md`.

## Filing an issue

Say what you asked the agent, what it did, and what you expected, and which skill
it was in if you know: finding-patterns, adjusting, design, planning,
implementing, verifying, values, conventions, decisions or accessibility. The checklist it produced is the most useful thing
to paste, with names made neutral. If the complaint is that nothing happened,
say so, and say what the agent reported it could not read.

## Before you open a pull request

`.claude/rules/uic-pr.md` is the full order. The short form:

1. `scripts/gate.sh`.
2. Simplify what you wrote, then run the gate again if it changed anything.
3. A correctness review and a security review, both of them, every time.
4. Read the documents `.claude/rules/uic-docs.md` lists against your change,
   and say in the pull request body which you read and what you found. **"Read,
   nothing false" is a result.** Fix what is wrong, and wherever it was copied.
5. If a skill changed, the one fresh read of its changed lines
   (`.claude/skills/uic-writing/SKILL.md`, *After writing*).
6. `scripts/gate.sh` again, if anything above changed a file.
7. Fill every section of the pull request template — who produced the change
   and with what, that you searched open and closed pull requests, and how it
   stays inside what `docs/concept.md` says this is not. **A person reads the
   complete diff before it is opened**, and a pull request carrying unrelated
   changes is split rather than reviewed.

## Reading order

`docs/concept.md` first — the problem and why. Then `.claude/CLAUDE.md` for the
ideas the design rests on.
