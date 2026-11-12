#!/usr/bin/env bash
# Each check is proved to fail on what it exists to catch, and to pass without
# it: a defect is planted in a copy of the repository, and the check is run
# both ways. Every guard in this repository written without such a proof has
# since been found not to fire.

set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
passed=0
failed=0

# A fresh copy of the repository's files: tracked and new, not ignored.
copy() {
  local to
  to=$(mktemp -d "$work/copy.XXXXXX")
  (cd "$here" && git ls-files -co --exclude-standard | while read -r f; do [ -e "$f" ] && printf '%s\n' "$f"; done \
    | tar cf - -T -) | tar xf - -C "$to"
  printf '%s' "$to"
}

# expect <pass|fail> <what> <check> <dir>
expect() {
  local want=$1 what=$2 check=$3 dir=$4 got
  if UIC_ROOT="$dir" bash "$here/scripts/$check" >/dev/null 2>&1; then got=pass; else got=fail; fi
  if [ "$got" = "$want" ]; then
    passed=$((passed + 1))
  else
    echo "  $check should $want on: $what" >&2
    failed=$((failed + 1))
  fi
}

# edit <dir> <file> <perl substitution over the whole file>
edit() { perl -0777 -i -pe "$3" "$1/$2"; }

# --- check-skills.sh ---------------------------------------------------------
c=$(copy); expect pass "the repository as it is" check-skills.sh "$c"
c=$(copy); edit "$c" skills/values/SKILL.md 's/Use when/Invoke if/'
expect fail "a description that does not say when to use it" check-skills.sh "$c"
c=$(copy); edit "$c" skills/values/SKILL.md 's/^description: .*$/"description: " . ("x" x 1030) . " Use when"/me'
expect fail "a description over 1,024 characters" check-skills.sh "$c"
c=$(copy); edit "$c" skills/values/SKILL.md 's/^(description: For what the end user sees) — /$1: /m'
expect fail "front matter YAML would not parse" check-skills.sh "$c"
c=$(copy); edit "$c" skills/design/SKILL.md 's/^name: design$/name: drawing/m'
expect fail "a name that is not its directory" check-skills.sh "$c"
c=$(copy); printf '%s\n' "$(printf 'x%.0s' $(seq 1 16001))" >> "$c/skills/planning/SKILL.md"
expect fail "a SKILL.md over 16,000 characters" check-skills.sh "$c"
c=$(copy); for _ in $(seq 1 500); do echo >> "$c/skills/planning/SKILL.md"; done
expect fail "a body of 500 lines or more" check-skills.sh "$c"
c=$(copy); echo '[gone](missing.md)' >> "$c/skills/planning/SKILL.md"
expect fail "a link to a file that does not exist" check-skills.sh "$c"
c=$(copy); echo 'See `## Nowhere`.' >> "$c/skills/planning/SKILL.md"
expect fail "a section no template defines" check-skills.sh "$c"
c=$(copy); echo 'Then `ui-consistency:nothing`.' >> "$c/skills/planning/SKILL.md"
expect fail "a skill name that points at nothing" check-skills.sh "$c"
c=$(copy); edit "$c" hooks/session-context.md 's/ui-consistency:accessibility/accessibility/'
expect fail "session text that leaves a skill out" check-skills.sh "$c"
c=$(copy); echo '[rare](../decisions/rare.md)' >> "$c/skills/planning/SKILL.md"
expect fail "a link from another skill into decisions" check-skills.sh "$c"
c=$(copy); echo 'See `../decisions/rare.md`.' >> "$c/skills/planning/SKILL.md"
expect fail "a path from another skill into decisions, written out" check-skills.sh "$c"
c=$(copy); echo '[calibration](../verifying/calibration.md)' >> "$c/skills/planning/SKILL.md"
expect fail "a link that leaves its skill" check-skills.sh "$c"
c=$(copy); echo 'See `../verifying/gone.md`.' >> "$c/skills/planning/SKILL.md"
expect fail "a written-out path to a file that does not exist" check-skills.sh "$c"
c=$(copy); echo 'Use the Snackbar.' >> "$c/skills/design/SKILL.md"
expect fail "a library component's name" check-skills.sh "$c"

# --- check-packaging.sh ------------------------------------------------------
c=$(copy); expect pass "the repository as it is" check-packaging.sh "$c"
c=$(copy); edit "$c" .codex-plugin/plugin.json 's/"version": "[^"]*"/"version": "9.9.9"/'
expect fail "a manifest behind the version" check-packaging.sh "$c"
c=$(copy); edit "$c" gemini-extension.json 's/"description": "/"description": "Other: /'
expect fail "a manifest describing the plugin another way" check-packaging.sh "$c"
c=$(copy); edit "$c" hooks/hooks.json 's/"timeout": \d+/"timeout": 30/'
expect fail "a hook allowed more than 5 seconds" check-packaging.sh "$c"
c=$(copy); edit "$c" .cursor-plugin/plugin.json 's/"license": "MIT"/"license": "ISC"/'
expect fail "a manifest with another licence" check-packaging.sh "$c"
c=$(copy); edit "$c" plugin.json 's/"version": "[^"]*"/"version": "9.9.9"/'
expect fail "Copilot CLI's manifest behind the version" check-packaging.sh "$c"
c=$(copy); edit "$c" plugin.json 's{^\{}{\{\n  "\$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",}'
expect fail "Copilot CLI's manifest opted into Agent Plugins" check-packaging.sh "$c"
c=$(copy); edit "$c" plugin.json 's/"description": "/"description": "Other: /'
expect fail "Copilot CLI's manifest describing the plugin another way" check-packaging.sh "$c"
c=$(copy); edit "$c" plugin.json 's/"license": "MIT"/"license": "ISC"/'
expect fail "Copilot CLI's manifest with another licence" check-packaging.sh "$c"
c=$(copy); edit "$c" .codex-plugin/plugin.json 's/"skills": "\.\/skills\/"/"skills": ".\/skills\/",\n  "hooks": {}/'
expect fail "a Codex manifest with a hooks entry" check-packaging.sh "$c"
c=$(copy); edit "$c" .codex-plugin/plugin.json 's/"shortDescription": "/"shortDescription": "Much longer than thirty characters: /'
expect fail "a listing subtitle over OpenAI's 30 characters" check-packaging.sh "$c"
c=$(copy); edit "$c" .codex-plugin/plugin.json 's/"logo": "[^"]*"/"logo": ".\/assets\/gone.svg"/'
expect fail "a listing logo that is not in the repository" check-packaging.sh "$c"
c=$(copy); echo '{}' > "$c/package.json"
expect fail "a package.json an install would run npm on" check-packaging.sh "$c"
c=$(copy); mkdir "$c/bin"
expect fail "a top-level bin/" check-packaging.sh "$c"
c=$(copy); cp "$c/.claude/CLAUDE.md" "$c/CLAUDE.md"
expect fail "a CLAUDE.md at the plugin root" check-packaging.sh "$c"

# --- check-hook.sh -----------------------------------------------------------
c=$(copy); expect pass "the repository as it is" check-hook.sh "$c"
c=$(copy); printf '%s\n' "$(printf 'y%.0s' $(seq 1 60))" >> "$c/hooks/session-context.md"
expect fail "session text of 1,750 characters or more" check-hook.sh "$c"
c=$(copy); edit "$c" hooks/session-start 's/\{"additional_context": "%s"\}/{"additional_context": "%s", "additionalContext": "%s"}/'
expect fail "an answer in two shapes at once" check-hook.sh "$c"
c=$(copy); edit "$c" hooks/session-start 's/\[ -z "\$\{COPILOT_CLI:-\}" \]/true/'
expect fail "Copilot answered in Claude Code's shape" check-hook.sh "$c"
c=$(copy); edit "$c" hooks/session-start 's/\[ -z "\$\{COPILOT_CLI:-\}" \]/[ -z "\${COPILOT_CLI:-}" ] \&\& [ -z "\${PLUGIN_ROOT:-}" ]/'
expect fail "Codex answered in another shape" check-hook.sh "$c"
c=$(copy); edit "$c" hooks/session-start 's/^escaped=.*$/escaped=\$context/m'
echo 'A "quoted" word.' >> "$c/hooks/session-context.md"
expect fail "text that is not escaped for JSON" check-hook.sh "$c"
c=$(copy); edit "$c" hooks/session-start 's/^set -euo pipefail$/set -euo pipefail\nexit 3/m'
expect fail "a hook that exits non-zero" check-hook.sh "$c"

# --- check-private-names.sh --------------------------------------------------
repo_of() { (cd "$1" && git init -q && git add -A && git -c user.email=t@t -c user.name=t commit -qm copy) >/dev/null; }
# Names made up here, so none of them is written in any file of the copy.
absent="zq$RANDOM$RANDOM-absent"
planted="zq$RANDOM$RANDOM-planted"
c=$(copy); echo "A line naming $planted." >> "$c/README.md"; repo_of "$c"
echo "$planted" > "$work/names-present"
printf '# a comment\n\n%s\n' "$absent" > "$work/names-absent"
UIC_PRIVATE_NAMES="$work/names-present" expect fail "a listed name in a file" check-private-names.sh "$c"
UIC_PRIVATE_NAMES="$work/names-absent" expect pass "no listed name anywhere" check-private-names.sh "$c"
UIC_PRIVATE_NAMES="$work/no-list-here" expect pass "no list at all, said out loud" check-private-names.sh "$c"
c=$(copy); : > "$c/skills/$planted-notes.md"; repo_of "$c"
UIC_PRIVATE_NAMES="$work/names-present" expect fail "a listed name in a path" check-private-names.sh "$c"

# --- version-check.sh --------------------------------------------------------
# A repository of its own: the check compares the working tree with origin/main.
vrepo() {
  local r
  r=$(mktemp -d "$work/version.XXXXXX")
  mkdir -p "$r/.claude-plugin" "$r/skills"
  echo '{ "name": "uic", "version": "1.0.0" }' > "$r/.claude-plugin/plugin.json"
  echo 'a' > "$r/skills/one.md"
  (cd "$r" && git init -q -b main && git add -A && git -c user.email=t@t -c user.name=t commit -qm first \
    && git update-ref refs/remotes/origin/main "$(git rev-parse HEAD)")
  printf '%s' "$r"
}
# vexpect <pass|fail> <what> <dir> <text the output must carry>
vexpect() {
  local want=$1 what=$2 dir=$3 carry=$4 out got
  if out=$(cd "$dir" && bash "$here/scripts/version-check.sh" 2>&1); then got=pass; else got=fail; fi
  if [ "$got" = "$want" ] && [[ "$out" == *"$carry"* ]]; then
    passed=$((passed + 1))
  else
    echo "  version-check.sh should $want, saying '$carry', on: $what" >&2
    failed=$((failed + 1))
  fi
}
unreleased='# Release Notes\n\n## Unreleased\n\n- a fix\n\n## v1.0.0 (2026-01-01)\n\n- first\n'
empty='# Release Notes\n\n## Unreleased\n\n## v1.0.0 (2026-01-01)\n\n- first\n'
released='# Release Notes\n\n## Unreleased\n\n## v1.0.1 (2026-01-02)\n\n### Fixes\n\n- a fix\n\n## v1.0.0 (2026-01-01)\n\n- first\n'

# A change: it says so under Unreleased and leaves the version alone.
r=$(vrepo); echo 'b' > "$r/skills/one.md"; printf "$empty" > "$r/RELEASE-NOTES.md"
vexpect fail "a shipped change not committed yet, nothing under Unreleased" "$r" "says nothing under '## Unreleased'"
r=$(vrepo); echo 'b' > "$r/skills/one.md"; printf "$empty" > "$r/RELEASE-NOTES.md"
(cd "$r" && git checkout -qb branch && git add -A && git -c user.email=t@t -c user.name=t commit -qm change)
vexpect fail "a shipped change that is committed, nothing under Unreleased" "$r" "says nothing under '## Unreleased'"
r=$(vrepo); echo 'b' > "$r/skills/one.md"
vexpect fail "a shipped change with no release notes at all" "$r" "says nothing under '## Unreleased'"
r=$(vrepo); echo '{ "name": "uic", "version": "1.0.0" }' > "$r/plugin.json"
(cd "$r" && git add -A && git -c user.email=t@t -c user.name=t commit -qm copilot && git update-ref refs/remotes/origin/main "$(git rev-parse HEAD)")
echo '{ "name": "uic", "version": "1.0.0", "keywords": ["a"] }' > "$r/plugin.json"; printf "$empty" > "$r/RELEASE-NOTES.md"
vexpect fail "Copilot CLI's manifest changed, nothing under Unreleased" "$r" "says nothing under '## Unreleased'"
r=$(vrepo); echo 'a' > "$r/USING.md"
(cd "$r" && git add -A && git -c user.email=t@t -c user.name=t commit -qm using && git update-ref refs/remotes/origin/main "$(git rev-parse HEAD)")
echo 'b' > "$r/USING.md"; printf "$empty" > "$r/RELEASE-NOTES.md"
vexpect fail "USING.md changed, nothing under Unreleased" "$r" "says nothing under '## Unreleased'"
r=$(vrepo); echo 'b' > "$r/skills/one.md"; printf "$unreleased" > "$r/RELEASE-NOTES.md"
vexpect pass "a shipped change with its line under Unreleased" "$r" "under '## Unreleased'"

# A release: the version moves once, with its section, and Unreleased emptied.
r=$(vrepo); echo 'b' > "$r/skills/one.md"; echo '{ "name": "uic", "version": "1.0.1" }' > "$r/.claude-plugin/plugin.json"
printf "$released" > "$r/RELEASE-NOTES.md"
vexpect pass "a release with its section, before it is committed" "$r" "a release"
r=$(vrepo); echo '{ "name": "uic", "version": "1.0.1" }' > "$r/.claude-plugin/plugin.json"
printf '# Release Notes\n\n## Unreleased\n\n- left behind\n\n## v1.0.1 (2026-01-02)\n\n- a fix\n\n## v1.0.0 (2026-01-01)\n\n- first\n' > "$r/RELEASE-NOTES.md"
vexpect fail "a release that leaves lines under Unreleased" "$r" "still has lines"
for changelog in '' '## v1.0.10 (2026-01-02)\n\n- another\n' '## v1.0.1 (2026-01-02)\n\n## v1.0.0 (2026-01-01)\n\n- first\n' \
  '## v1.0.1 (2026-01-02)\n\n### Fixes\n\n## v1.0.0 (2026-01-01)\n\n- first\n'; do
  r=$(vrepo); echo 'b' > "$r/skills/one.md"; echo '{ "name": "uic", "version": "1.0.1" }' > "$r/.claude-plugin/plugin.json"
  [ -z "$changelog" ] || printf "$changelog" > "$r/RELEASE-NOTES.md"
  vexpect fail "a moved version whose notes say nothing: [${changelog:0:24}]" "$r" "no entry in RELEASE-NOTES.md"
done
r=$(vrepo); echo 'docs only' > "$r/README.md"
vexpect pass "only unshipped files changed" "$r" "no release note needed"
r=$(vrepo); (cd "$r" && git update-ref -d refs/remotes/origin/main); echo 'b' > "$r/skills/one.md"
vexpect pass "no origin/main to compare against" "$r" "skipping the version check"

# --- bump.sh -----------------------------------------------------------------
# Cutting a release moves every manifest and takes what waited under Unreleased.
c=$(copy); edit "$c" RELEASE-NOTES.md 's/^## Unreleased\n/## Unreleased\n\n- a line waiting for the release\n/m'
before=$(perl -MJSON::PP -e 'local $/; open my $h, "<", "'"$c"'/.claude-plugin/plugin.json"; print JSON::PP->new->decode(<$h>)->{version}')
if UIC_ROOT="$c" bash "$here/scripts/bump.sh" minor >/dev/null 2>&1 \
  && UIC_ROOT="$c" bash "$here/scripts/check-packaging.sh" >/dev/null 2>&1 \
  && perl -0777 -ne 'exit !(/^## Unreleased\n\n## v\d+\.\d+\.0 \(\d{4}-\d\d-\d\d\)\n\n- a line waiting for the release\n/m)' "$c/RELEASE-NOTES.md" \
  && [ "$(perl -MJSON::PP -e 'local $/; open my $h, "<", "'"$c"'/.claude-plugin/plugin.json"; print JSON::PP->new->decode(<$h>)->{version}')" != "$before" ]; then
  passed=$((passed + 1))
else
  echo "  bump.sh should move every manifest and turn Unreleased into the new version's section" >&2
  failed=$((failed + 1))
fi

echo "checks proved: $passed of $((passed + failed)) plants caught or passed as they should"
[ "$failed" = 0 ]
