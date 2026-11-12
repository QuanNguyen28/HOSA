# Documents

## A wrong statement is corrected, not annotated

Replace it with what is true now. Git and the private archive repository are
the record; a document carries only the present. If the wrong version was
copied elsewhere, fix the copies in the same change — search for them.

## Evidence from a private repository keeps its numbers and loses its names

This tool is dogfooded against private repositories. The **numbers** from
those runs are worth writing down; the **names** are not publishable.

**Before a measurement is written down anywhere, rename every project-specific
identifier to a neutral equivalent of the same shape** — same casing, same word
count, same dialect. `OrdersGrid` for a PascalCase grid, `app-orders-grid` for
its selector form, `acme-orders-page` for a test-id.

A renamed fixture must still exercise what it was written for: rename the
segments of a multi-segment alias or a deep path, never collapse them.

`scripts/check-private-names.sh` enforces it. It reads a list from
`UIC_PRIVATE_NAMES`, or `~/.config/uic/private-names.txt`, and fails on any
match in a tracked file's **path or contents**. The list is never committed — a
committed denylist is itself the leak — so where there is no list the check says
so and passes. The list carries every spelling of a name, one per line; a guess
at another casing is how a real occurrence slips through.

## Public text says nothing about where or how the owner works

The repository, its issues, PR bodies, comments and commit messages are public,
and GitHub's edit history keeps what was replaced. None of them says anything
about the owner rather than the plugin: their machines, their workplace, their
projects and how those are built, local apps and paths, where and how testing
happens.

- What to test goes into an issue as acceptance criteria — *what* is checked,
  never where or on which projects.
- Evidence from real work keeps its numbers, described by role.
- `scripts/check-private-names.sh` covers names in tracked files only. An issue, a
  PR body or a comment has no test: reread the exact text before sending it.

## The documents this applies to

`.claude/CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `USING.md`,
`docs/concept.md`, `.claude/rules/*.md`, and every skill with its supporting
files.

Before opening a PR, read them against the change and say in the body which
were read and what was found. "Read, nothing false" is a result.
