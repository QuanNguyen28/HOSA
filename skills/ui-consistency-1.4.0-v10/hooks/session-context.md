ui-consistency — for anything the end user will see, these join the phases of
whatever process is already running, and run the phases themselves when none is.
Use them without being asked.

- A new page or feature, or a refactor across pages:
  ui-consistency:finding-patterns → ui-consistency:planning
  → ui-consistency:implementing → ui-consistency:verifying
- A small change to one page: ui-consistency:adjusting → implementing
  → verifying. The check is never the part that gets dropped.
- Checking code already written: verifying — after finding-patterns where no
  checklist exists yet.
- A page's design, or one to agree before building: ui-consistency:design.
- Called by the phases when a step needs them: ui-consistency:values,
  ui-consistency:conventions, ui-consistency:decisions.
- An accessibility standard, only when asked or required by the project:
  ui-consistency:accessibility.

If a process running this work has a spec or plan, add to it, and run
finding-patterns before its first task that changes what the user sees is handed
to anyone, whichever process wrote it. Decide by the order the skills carry and
report what settled each decision. Ask only about a request that says two things
or leaves open what the page must show; a tie whose change reaches outside the
task; and a component the request did not name with its place, or code extracted
into one.

If the person says a page came out wrong, or fixes one by hand, offer once to
draft a report for
https://github.com/kamenkurtev/ui-consistency/issues/new?template=a_page_came_out_wrong.yml:
what was asked, what was decided and what settled it, what came out wrong, with
every project name renamed to a neutral one. The person posts it, never you.
