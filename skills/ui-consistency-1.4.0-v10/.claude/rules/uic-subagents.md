# Subagents

Working on this repository, the main session keeps its own model and
orchestrates. It splits the work, briefs each subagent, and checks what comes
back.

- **Work inline by default.** Spawn a subagent only for one of these:
  - work whose output would flood the main context;
  - work that is self-contained and can come back as a summary;
  - the one fresh read of a changed skill
    (`.claude/skills/uic-writing/SKILL.md`, *After writing*);
  - a subagent the owner asks for.
- **Pass `model` on every spawn**, chosen for the job.
  - `haiku`: searching, reading, listing, summarising.
  - `sonnet`: writing, reviewing and checking. This is most work, the fresh
    read included.
  - `opus`: only for hard reasoning. Say why.
- `.claude/settings.json` sends a subagent with no model of its own to
  `sonnet`. It has none of its own when no model is passed and its definition
  names none.
- Explore and Plan ignore that setting and run on the main session's model,
  unless you pass `model` when you spawn them.
- **At most one `opus` subagent at a time.** A fork counts as one: it runs on
  the main session's model and carries the whole context.
- **At most three subagents in parallel**, and only for independent work. Why
  the reviews run inline is `uic-pr.md`, *How the reviews are done*.
- **Ask each subagent for a short result**: its findings, paths and numbers, and
  what it changed. Never ask for a transcript: what it returns lands in the main
  context.
- **Check a result before using it.** Never report a subagent's "done" as done.
  - Read the diff of what it changed, against what it was asked to do.
  - Check one or two of its claims yourself, such as a path, a count or a quoted
    line.
  - If it changed a file, run `scripts/gate.sh` yourself.
  - If the result falls short, send it back once with what is wrong, or fix it
    in the main session.
- **No agent teams unless the owner asks.** Teammates run on `sonnet`.
