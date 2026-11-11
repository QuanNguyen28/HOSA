#!/usr/bin/env bash
# Evidence from a private repository keeps its numbers and loses its names
# (.claude/rules/uic-docs.md). This fails on any name from the list in a tracked
# file's path or contents.
#
# The list lives outside the repository, because a committed denylist is itself
# the leak: one name per line, `#` for a comment, at
# ~/.config/uic/private-names.txt or wherever UIC_PRIVATE_NAMES points. Absent —
# on CI, on anybody else's machine — this passes and says so.
#
# A name is spelled several ways and the list carries each: nothing here
# derives one dialect from another.

set -euo pipefail
cd "${UIC_ROOT:-$(dirname "$0")/..}"

list="${UIC_PRIVATE_NAMES:-$HOME/.config/uic/private-names.txt}"
if [ ! -r "$list" ]; then
  # Not a silent skip: the one thing worse than no guard is a guard everybody
  # believes is running.
  echo "private names: no list at $list — not checked"
  exit 0
fi

patterns=$(mktemp)
trap 'rm -f "$patterns"' EXIT
sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$list" | grep -v -e '^#' -e '^$' > "$patterns" || true
if [ ! -s "$patterns" ]; then
  echo "private names: the list at $list is empty — not checked"
  exit 0
fi

# The path is evidence too: a directory called after a private library leaks
# it whether or not any file says the word.
paths=$(git ls-files | grep -i -F -f "$patterns" || true)
contents=$(git grep -I -i -F -l -f "$patterns" || true)

if [ -n "$paths$contents" ]; then
  [ -z "$paths" ] || printf 'a private name in the path: %s\n' $paths >&2
  [ -z "$contents" ] || printf 'a private name in the file: %s\n' $contents >&2
  exit 1
fi
echo "private names: $(wc -l < "$patterns" | tr -d ' ') names, none in a tracked path or file"
