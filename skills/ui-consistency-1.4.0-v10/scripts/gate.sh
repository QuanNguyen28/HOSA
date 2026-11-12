#!/usr/bin/env bash
# Everything a pull request needs. Bash and perl, both of which come with git;
# nothing to install.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> skills"
bash scripts/check-skills.sh

echo "==> packaging"
bash scripts/check-packaging.sh

echo "==> hook"
bash scripts/check-hook.sh

echo "==> private names"
bash scripts/check-private-names.sh

# A change that ships waits under Unreleased for the next release, and a
# release says what it releases. Without a gate, both were forgotten — twice in
# one day before it existed.
echo "==> version"
bash scripts/version-check.sh

# Every guard in this repository written without a proof that it fires has
# since been found not to. Each check above is run here on a copy with a
# planted defect, and on one without.
echo "==> the checks catch what they are for"
bash scripts/test-checks.sh

# Strict, as Anthropic's directory asks before a submission: a warning fails.
# The repository as a marketplace, and the plugin's own manifest, which the
# marketplace check does not look inside.
echo "==> plugin validate"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate . --strict
  claude plugin validate .claude-plugin/plugin.json --strict
else
  echo "claude CLI not found; skipping plugin validate"
fi

echo "gate passed"
