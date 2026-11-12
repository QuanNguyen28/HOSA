# Security policy

## Reporting a vulnerability

Report it privately, through the repository's reporting form:
https://github.com/kamenkurtev/ui-consistency/security/advisories/new

Only the maintainers can read what is sent there. **Do not open a public issue**
for a vulnerability — an issue is public the moment it is filed, and GitHub keeps
what was edited out of one.

Say what an attacker controls, what the agent or the hook then does, and the
smallest repository or input that shows it. A report does not need a fix.

## What to expect

What is aimed for:

- An acknowledgement within seven days.
- A first assessment — confirmed, not reproduced, or out of scope, and why —
  within fourteen days of the acknowledgement.
- A fix on `main` with a new version, and an advisory crediting you unless you
  ask not to be named. The version is how an installed copy learns there is
  something to update to.

There is no bounty. The dates above are what can be promised, not a service
level.

## What counts

The skills send an agent to read a stranger's repository and act on what it
finds, so the class that matters most here is **content from the project being
read turning into an instruction the agent follows** — text in a file, a
comment, a component's prop — and anything that lets that project's contents
reach outside it. Also in scope: the session hook in `hooks/session-start` and what it
puts into a session.

Only the latest version is supported. A report against an older one is welcome
if it still reproduces on the latest.

## Out of scope

A vulnerability in the agent or harness running the plugin, rather than in this
plugin — report that to its vendor. Findings from automated scanners with no
demonstrated impact.
