# Contributing

Backend Design is opinionated by design. Contributions are welcome, but the bar is "does this make Claude code more like a senior backend engineer?" not "is this a complete reference?"

## What belongs in this plugin

- A reflex a senior applies but a junior forgets (idempotence, EXPLAIN before merge, deny-by-default).
- A workflow that catches incidents at design time (`think-before-coding` style).
- A discipline that is enforceable at write time (a hook that warns on a concrete anti-pattern).
- An opinion that can be defended with a one-line reason and a deviation rule.

## What does not belong

- Documentation Claude already has (HTTP status codes, what Redis is, OAuth flow diagrams).
- Framework-specific recipes (use the framework's docs).
- "Add this for completeness" content. If it does not change behavior, it pollutes context.
- Tiered advice ("it depends"). Pick a position, defend it, name when to deviate.

## How to propose a change

1. Open an issue first for anything bigger than a typo or a one-line clarification. Describe the reflex, the anti-pattern, or the discipline you want the plugin to teach, and which existing skill / agent / hook it lives in or extends.
2. For a new skill, the issue should answer: what reflex does it teach, who is the target user phrasing that should trigger it, and what existing skill would it overlap with.
3. For a new hook rule, the issue should include one concrete bad code example, one concrete good code example, and the regex or detection logic you propose.
4. For a new agent, the issue should explain why a skill plus inline behavior is not enough.

## Style rules

The plugin's existing skills are the style guide. Match them.

- 80 to 200 lines per skill, dense. Over 250 is encyclopedic; trim.
- Sharp openings that name the stake.
- "The Discipline" section with 3 to 6 numbered checks.
- Anti-patterns with concrete examples.
- Quick decision guide as a table.
- See also section with `[[skill-name]]` cross-references.
- No marketing words ("comprehensive", "robust", "scalable", "powerful").
- Opinions stated, not hedged. Each opinionated default ends with a deviation rule.

## How to test a change

The plugin includes its own test fixtures via the hooks.

Hook smoke tests (Python 3.8+ required):

```bash
# Migration hook
echo '{"tool_name":"Write","tool_input":{"file_path":"db/migrations/x.sql","content":"<sql>"}}' \
  | python hooks/check_migration.py

# Backend component hook
echo '{"tool_name":"Write","tool_input":{"file_path":"src/handlers/x.ts","content":"<code>"}}' \
  | python hooks/check_backend_component.py

# Security hook
echo '{"tool_name":"Write","tool_input":{"file_path":"src/x.py","content":"<code>"}}' \
  | python hooks/check_security.py
```

For any new hook rule, include in the PR:

- One JSON payload that should trigger the warning (positive case).
- One JSON payload that should stay silent (negative case).
- Both verified to behave correctly.

For skill content changes, the easiest test is real use: run the modified plugin against a representative prompt and confirm the behavior changes the way you intend.

## Validating the plugin

Before submitting a PR:

```bash
claude plugin validate /path/to/backend-design
```

The validator catches manifest issues, frontmatter problems, and broken hooks.json. PRs should leave the plugin passing with zero warnings.

## What gets rejected

- Skills that explain syntax instead of teaching a reflex.
- Soft opinions ("you might consider", "it can be a good idea to").
- Changes that grow a skill past 250 lines without splitting.
- Hook rules with no positive / negative test cases.

## Reporting issues

For bugs in hooks (false positives, false negatives), include:

- The exact stdin JSON that produced the wrong behavior.
- What the hook printed (or did not print).
- What the expected behavior is.
- Your Python version and OS.

For weak skill triggering ("Claude should have invoked this skill but did not"):

- The exact user prompt that did not trigger the skill.
- Which skill you expected.
- What Claude did instead.

For content disagreements ("this opinion is wrong"):

- The skill and section.
- A concrete counterexample, not "it depends".
- A proposed replacement opinion, with its deviation rule.

## License

By contributing you agree that your contribution is licensed under the MIT License of this project.
