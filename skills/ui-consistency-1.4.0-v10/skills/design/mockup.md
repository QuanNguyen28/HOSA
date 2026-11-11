# A mockup of the page-to-be

**Read when:** `design` step 4 — a person asks to see the page before it is
written, or asks for alternatives. Never otherwise.

It shows **whether the page hangs together**, drawn with the project's values:
the checklist's, where one exists; otherwise read from the theme as
`ui-consistency:values` says. Nothing new is measured.

## What it is

- **One self-contained HTML document**, with inline styles.
- Its `:root` carries the values resolved: the theme's entries, the
  spacing base and the gaps, each position's type bundle, the radius, the
  heights of controls, rows and bars.
- Embed every image: an SVG as markup, a raster as a data URI.
- **No relative path to anything**, so the same file works opened directly,
  served, or attached to a task.
- Show **the roles in their order, at the sizes the family writes**: which
  holders, what stands in each, how the regions are spaced, what the text looks
  like at each position.
- If alternatives are asked for, draw two or three arrangements of the same
  roles, each labelled, in the same document.

## What it must not do

- **Never an imitation of a piece the project has.** Draw a region as a plain
  box at **the measured values** — the control height the family writes, the
  radius and border from the theme, the label's type bundle.
- **Label it with the project's own piece** for that role. Never draw it to look
  like the project's field or button.
- **No behaviour.** No hover, focus, error state, animation or interaction.
- **It says what it is, on its face**: a line at the top of the document — *a
  static arrangement with this project's values, not its components*.
- **Nothing invented.** Draw a value that could not be resolved as unresolved —
  marked, with what was missing. Never fill it with something plausible.
- **Never read back.** Values go into it from the theme; nothing is ever taken
  out of it ([reading.md](reading.md), *A design's values*).

## Three levels, and the question each answers

| | Answers | Where |
|---|---|---|
| **The arrangement** | the right roles, in the right order, at the right sizes | this document |
| **One control's look and behaviour** | what the real piece does | wherever the project already renders its real components — a component catalogue, a demo page, the running application. **Point at it; never redraw it** |
| **The real thing** | does the page match | the application, and `ui-consistency:verifying` |

## Where it is shown

The document is the same in every case; only how it is looked at changes.
**Nothing is written inside the working copy**, in any of them.

1. **A visual companion is already running** — another process with a browser
   channel. Write the document where that serves from.
   - A complete document is served as it is, so the project's values keep their
     own styling.
   - Patch nothing in the companion, and ask it to change nothing.
2. **Nothing is running.** Write the document to a newly created directory
   outside the working copy, and open it the way the platform opens a file.
   - To iterate, a one-command static server there and a few lines of polling in
     the document reload it as it is rewritten.
3. **No browser** — remote, headless. Report the path. Never say it was shown.
