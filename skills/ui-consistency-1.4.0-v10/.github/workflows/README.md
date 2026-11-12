# What runs on GitHub

Two workflows.

- **`release.yml`**, on a push to `main`: tags the version in `plugin.json` as
  `v<version>`, publishes its section of `RELEASE-NOTES.md` as a GitHub
  Release, and moves the `release` branch to it — the first time that version
  reaches `main`. Anthropic's directory follows `release`.
- **`gate.yml`**, on every pull request and push: one job, `scripts/gate.sh`, the
  same script the rules require before opening a PR. The checks of the skills,
  the manifests, the hook and private names, the release note under *Unreleased*
  or the release's own section, the proof that each check fires, and `claude
  plugin validate` where the CLI is available. Nothing is installed: bash and
  perl are on the runner.

Three parts of the gate cannot run here and are stated rather than pretended:

- **`claude plugin validate`** is skipped when the CLI is absent, which it is
  on a runner, so nothing there validates a manifest's shape.
  `scripts/check-packaging.sh` compares fields across the manifests — version,
  description, licence, where the skills are — and checks the Codex manifest's
  `hooks` entry and listing fields, and nothing more.
- **The three reviews** — simplification, correctness, security — are in
  `.claude/rules/uic-pr.md` and are done by whoever opens the PR. A workflow
  cannot do them, and pretending otherwise would be worse than the gap.
- **Real work.** A skill change is checked by feedback the next time the plugin
  is used for real work (`AGENTS.md`, *Skill Changes Come From Real Work*), and a workflow
  cannot do that either.
