# Privacy

UI Consistency (`ui-consistency`) collects no data, stores no data, and sends no
data anywhere.

## What it reads

- **The skills** are instructions. The coding agent you already use, in your own
  session, follows them and reads your project's files — its pages, components
  and theme — to write a new page the way the others are written. That reading
  happens on your machine, through your agent's own tools, like any other file
  your agent reads.
- **The session hook** prints a fixed text from the plugin's own files
  (`hooks/session-context.md`) at the start of a session. It reads nothing from
  your project; from your environment it reads only the variables that say which
  tool is running it, to answer in that tool's format.

## What it does not do

- It has no server, no account and no telemetry.
- It makes no network request, and sends nothing to its author or anyone else.
- It reads no credential, token or key.
- It writes nothing into your repository on its own; what your agent writes, you
  review and commit.
- It asks for and handles no personal data such as names, email addresses or
  postal addresses.

What your coding agent itself sends to its model provider is governed by that
provider's terms, not by this plugin.

## Contact

Questions about this policy: open an issue at
https://github.com/kamenkurtev/ui-consistency/issues.
