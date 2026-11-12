# Git rules

## Every change starts as an issue
- **Open the issue before the branch exists**, and put it on the board in `Todo`.
  The branch is named after it, the PR references it, and it closes when the PR
  merges.
- This is not ceremony. The board is the only place that shows what was decided
  and why without reading the diff, and the branch naming below already assumes
  an issue number exists.
- **Every issue carries acceptance criteria** — a `## Acceptance criteria`
  section of short, checkable statements (`- [ ]`) saying what is true when the
  work is done. Without them nobody can tell whether the PR finished the issue
  or only touched it.
  - They say **what** to verify, never where or on which projects it is tested:
    the repository is public.
  - **They name only what the pull request itself can meet.** None waits on
    later work, a later run, or feedback that has not come yet.
  - The PR says which criteria it meets. A criterion the work cannot meet is
    changed or dropped on the issue, visibly, before the merge.
- **An issue closes, and goes to `Done`, when its PR merges.** It never stays
  open waiting on anything after that.
- **Whether a change works in practice comes from feedback** — the owner's or
  another user's. Whether that feedback becomes a new issue is decided when it
  arrives, never in advance.
- **No issue needed** for a change made *inside* an issue already in progress and
  covered by its scope — a typo in the code you just wrote does not need its own
  number.
- If the work turns out bigger than the issue it started under, **widen the issue
  visibly** — edit its description and criteria — or open a new one. Never widen
  it silently.
- Work that starts as "while I'm here" is exactly what this rule is for.

## Branches
- **Never commit directly to `main`.** Always branch first.
- **Branch naming:** `<username>/<issue-number>-<short-description>`
  - Example: `kkurtev/1-contract-extraction`
  - Lowercase, words separated by `-`, keep the description short.
- One logical change per branch — don't mix unrelated work.

## Commits
- Write clear, imperative messages: `Extract prop conventions from reference`, not `fixed stuff`.
- Reference the issue when relevant — `#12`, and the number is this repository's.
- Commit and push on the issue branch as the work goes. Nothing reaches `main`
  except through a merged PR.

## Versions
- **Semantic versioning, for a plugin made of text:**
  - **patch** — a fix or clearer wording; the agent does the same;
  - **minor** — the agent does something new or different;
  - **major** — something a user depends on breaks: a skill renamed or removed,
    a different way to install.
- **A PR that changes what ships adds its line under `## Unreleased`** in
  `RELEASE-NOTES.md`, saying what somebody who installed the plugin will
  notice, and leaves the version alone.
  - The gate fails on a branch touching `hooks/`, `skills/`, `USING.md`,
    `GEMINI.md` or a manifest with nothing under *Unreleased*. `USING.md` and
    `GEMINI.md` are what a harness with no hook loads. Docs, scripts and rules
    alone need no line.
- **A release is cut when the owner decides**, as a PR of its own.
  - `scripts/bump.sh` (`minor` / `major` as above) moves the version in every
    file that carries it, and turns *Unreleased* into the new version's section.
    Do not edit the version by hand.
  - The gate fails on a moved version with no section, or with lines left under
    *Unreleased*.
- Six files carry the version: the manifest of each harness and the
  marketplace entry. Only `.claude-plugin/plugin.json` is read when a plugin
  updates, so the other five drift with nothing to complain — which is why the
  script exists.
- **Merging a release tags it.** `.github/workflows/release.yml` tags
  `v<version>`, publishes its section as a GitHub Release, and moves the
  `release` branch to it. An installed copy updates when `plugin.json` names a
  new version, so users receive releases, not every merge.
- **OpenAI's plugin directory takes a ZIP, not the repository.**
  - Every version uploaded is a new package version, which OpenAI reviews
    again before it is published.
  - Upload one when the skills change in substance, as with cursor.directory.
  - It refuses lifecycle hooks, so the package leaves `hooks/` out. It carries
    only the Codex manifest, the skills, the icon and the licence:
    `git archive --format=zip -o ui-consistency-<version>.zip v<version> -- .codex-plugin skills .claude-plugin/icon.svg LICENSE README.md`
- **Nobody commits to `release`.** Development stays trunk-based on `main`;
  `release` only ever points at the last release, and Anthropic's directory
  follows it.
- **To work on the latest**, add the local clone as the marketplace
  (`CONTRIBUTING.md`): every change applies at the next session, with no
  release.

## Pull requests
- What happens before a PR is opened, and in what order, is `uic-pr.md`.
- Open the PR against `main` with the template filled in.
- **Merge it once `scripts/gate.sh` and the GitHub `gate` check pass** and the body
  names the three reviews. The owner reads that as the review; do not stop to ask
  for permission to merge. Squash, with the PR number in the subject.
- `gh pr create` and `gh pr merge` go through GitHub's GraphQL API, whose limit is
  shared by every tool on the account. When it is exhausted, the REST API
  (`gh api repos/<owner>/<repo>/pulls`, `…/pulls/<n>/merge`) still works.
- If a session runs `superpowers:finishing-a-development-branch`, its choice is
  *push and create a PR*, merged as above.

## Cleanup
- After a branch is merged, delete it **only on the remote** (`origin`).
- **Keep the local branch** — never run `git branch -d` locally for cleanup.

## Project board
Work is tracked on GitHub Project #3 (`Todo` / `In Progress` / `Done`). Its
`Test` column is not used: nothing waits there after a merge.

- **When you start working on an issue, move it to `In Progress`.** Do this before the first commit, not after.
- **When its PR is merged, close the issue and move it to `Done`**, with the criteria as they stand on it. Both — a closed issue left in `Todo` is as misleading as an open one sitting in `Done`.
- Every issue you open goes on the board, in `Todo`.
- **Look an item up by repository as well as number.** The board also holds the
  archive repository's issues, and their numbers overlap with this one's.
- The board is GraphQL only. When the limit is exhausted, note the moves owed and
  make them when it resets.