#!/usr/bin/env bash
# Cut a release: move the shipped version in every file that carries it, and
# turn what waited under `## Unreleased` into the new version's section.
#
# The version lives in every manifest a harness reads, and only plugin.json is
# read when a plugin updates — so the others drift with nothing to complain.
#
# Usage: scripts/bump.sh [patch|minor|major]     (patch by default)
#   patch — a fix or clearer wording; the agent does the same
#   minor — the agent does something new or different
#   major — something a user depends on breaks

set -euo pipefail
cd "${UIC_ROOT:-$(dirname "$0")/..}"

FILES=(
  .claude-plugin/plugin.json
  .claude-plugin/marketplace.json
  .codex-plugin/plugin.json
  .cursor-plugin/plugin.json
  gemini-extension.json
  plugin.json
)

kind="${1:-patch}"
case "$kind" in
  patch|minor|major) ;;
  *) echo "Unknown release kind: $kind" >&2; echo "Usage: scripts/bump.sh [patch|minor|major]" >&2; exit 1 ;;
esac

current=$(perl -MJSON::PP -e 'local $/; open my $h, "<", ".claude-plugin/plugin.json" or die; print JSON::PP->new->decode(<$h>)->{version} // ""')
if ! [[ "$current" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "plugin.json has no usable version: $current" >&2
  exit 1
fi
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]} patch=${BASH_REMATCH[3]}
case "$kind" in
  major) next="$((major + 1)).0.0" ;;
  minor) next="$major.$((minor + 1)).0" ;;
  patch) next="$major.$minor.$((patch + 1))" ;;
esac

# Every file is checked before any is written, so a file that does not carry
# the version leaves the others as they were.
for file in "${FILES[@]}"; do
  grep -q "\"version\": \"$current\"" "$file" || { echo "$file does not carry version $current — fix it by hand." >&2; exit 1; }
done

# Textual rather than parse-and-serialise: these files are hand-edited, and
# reformatting them into a diff nobody asked for is its own annoyance.
for file in "${FILES[@]}"; do
  FROM="$current" TO="$next" perl -0777 -i -pe 's/"version": "\Q$ENV{FROM}\E"/"version": "$ENV{TO}"/' "$file"
  echo "  $file"
done

# The release takes what waited under Unreleased: the heading stays, empty, for
# the next one.
if ! grep -q '^## Unreleased$' RELEASE-NOTES.md; then
  echo "RELEASE-NOTES.md has no '## Unreleased' section to release." >&2
  exit 1
fi
NEXT="$next" DATE="$(date +%Y-%m-%d)" perl -0777 -i -pe 's/^## Unreleased\n/## Unreleased\n\n## v$ENV{NEXT} ($ENV{DATE})\n/m' RELEASE-NOTES.md
echo "  RELEASE-NOTES.md"

echo
echo "$current → $next. Read the v$next section in RELEASE-NOTES.md, and open the release as its own pull request;"
echo "merging it tags v$next."
