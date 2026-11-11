#!/usr/bin/env bash
set -euo pipefail

# Does this working tree change what ships without saying so in the release
# notes — and does a release say what it releases?
#
# A pull request that changes what ships adds its line under `## Unreleased` in
# RELEASE-NOTES.md and leaves the version alone. A release moves the version
# once and turns *Unreleased* into its own `## v<version> (<date>)` section
# (scripts/bump.sh does both), and merging it tags the release.
#
# Read against `origin/main` and against the **working tree** on both sides: a
# change you have made but not yet committed is a change. It does not skip when
# HEAD is origin/main: that is every branch with nothing committed yet, which is
# exactly when the gate is run.

SHIPPED='hooks/ skills/ USING.md GEMINI.md .claude-plugin/ .codex-plugin/ .cursor-plugin/ gemini-extension.json plugin.json'

if ! git rev-parse --verify --quiet origin/main >/dev/null; then
  # No network, a fresh clone, a detached head. A gate that cannot run offline
  # is a gate that gets skipped.
  echo "no origin/main to compare against; skipping the version check"
  exit 0
fi

# shellcheck disable=SC2086
CHANGED=$(git diff --name-only origin/main -- $SHIPPED)
if [ -z "$CHANGED" ]; then
  echo "nothing shipped changed; no release note needed"
  exit 0
fi

HERE=$(grep -o '"version": "[^"]*"' .claude-plugin/plugin.json || true)
THERE=$(git show origin/main:.claude-plugin/plugin.json 2>/dev/null | grep -o '"version": "[^"]*"' || true)

# say_under <heading prefix>: does RELEASE-NOTES.md have that section, with
# something other than a sub-heading under it?
said_under() {
  awk -v h="$1" '
    index($0, h) == 1 && (length($0) == length(h) || substr($0, length(h) + 1, 1) == " ") { found = 1; next }
    found && /^## / { exit }
    found && /^#/ { next }
    found && /[^[:space:]]/ { said = 1; exit }
    END { exit !(found && said) }
  ' RELEASE-NOTES.md 2>/dev/null
}

if [ "$HERE" = "$THERE" ]; then
  # A change, not a release: it waits under Unreleased for the next one.
  if ! said_under "## Unreleased"; then
    echo "this branch changes what ships and says nothing under '## Unreleased' in RELEASE-NOTES.md." >&2
    echo "Add a line there saying what somebody who installed the plugin will notice." >&2
    echo "The version moves only when a release is cut: scripts/bump.sh [patch|minor|major]." >&2
    exit 1
  fi
  echo "a change for the next release, under '## Unreleased'"
  exit 0
fi

# A release. The version is how an installed copy learns there is something
# new, and its section is how its user learns what.
VERSION=${HERE#\"version\": \"}
VERSION=${VERSION%\"}
if ! said_under "## v$VERSION"; then
  echo "version $VERSION has no entry in RELEASE-NOTES.md." >&2
  echo "Cut the release with scripts/bump.sh, which moves '## Unreleased' into a '## v$VERSION' section." >&2
  exit 1
fi
if said_under "## Unreleased"; then
  echo "version $VERSION is a release, but '## Unreleased' still has lines: move them into its section." >&2
  exit 1
fi

echo "a release: $THERE -> $HERE"
