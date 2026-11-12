---
name: ui-color-palette-penpot-generate-styles
description: Generate or sync Penpot local color styles from a UI Color Palette. Use when the user wants reusable local styles or swatches in Penpot.
argument-hint: <palette-id|current-palette> [sync]
---

# Generate Penpot Styles

Use this skill when the user wants a palette projected into **Penpot local color styles**.

Styles are useful for:

- visual swatch libraries
- reusable local colors in mockups
- quick inspection of palette output inside Penpot
- design review workflows based on visible style libraries

## Structure-first execution

Use this file as a workflow specification, not as an API catalog.

Execution order:

1. identify the target artifact: local styles
2. reduce the palette to the minimum style payload
3. apply the sync workflow
4. only then map the workflow to MCP or plugin API calls

The API layer is secondary to the workflow structure.

## Input contract

Before synchronization, the agent should ensure:

- a palette is already available in the active plugin or MCP context
- the target palette is selected explicitly or can be inferred as the current palette
- palette data includes stable palette, theme, color, and shade naming
- each shade exposes `hex`, `alpha`, and optional description

If one of these conditions is missing, resolve that upstream before style sync.

## Normalized PaletteData projection

Reduce `PaletteData` to a style-ready row model before execution:

- `paletteName`
- `themeName`
- `colorName`
- `shadeName` — includes `"source"` (the source/reference shade for each color family)
- `stylePath` (Penpot `LibraryColor.path`): segments joined with ` / ` (space-slash-space), **excluding** `shadeName`
  - no themes: `paletteName / colorName`
  - with themes: `paletteName / themeName / colorName` (theme name falls back to localized default if empty)
  - empty segments are filtered out
- `styleLeafName` (Penpot `LibraryColor.name`): the shade name only (e.g. `"80"`, `"source"`)
- `hex`: 6-character hex string — taken from **that theme's** `shade.hex`, not from the base or first theme (first 7 chars, e.g. `'#RRGGBB'`)
- `alpha`: opacity in `[0, 1]`

> The row model has **one row per `(themeName, colorName, shadeName)` triplet**. Arc and dark themes produce independent `hex` values for every shade. Never reuse the base or light theme's `hex` for a dark/arc theme's row — each row carries the independently-computed color for that theme.

This normalized row model is the actual handoff from palette structure to Penpot local style operations.

> **API note — `name` vs `path`**: `LibraryColor` exposes two separate string fields.
> - `name` = the leaf segment (shade name, e.g. `"80"` or `"source"`)
> - `path` = the folder path (e.g. `"UICP Color Primitives / Light / Primary"`)
>
> Set them **independently** when creating or updating. Do not concatenate them into a single `name` string.

## Sync behaviour

- Creates missing styles; finds existing ones by stored `id` before creating.
- Includes the `"source"` shade for each color family alongside the numbered scale steps.
- Sets `LibraryColor.path` and `LibraryColor.name` **independently** (see naming model below).
- `color` is set from `hex.substring(0, 7)` — use **the row's own `hex`** (the one where `themeName` matches the style's theme path segment). **Never reuse the base or light theme's `hex`** for a dark/arc themed style. Strips alpha channel from 8-char hex if present.
- `opacity` is set from `alpha` separately.
- Skips shades where `hex` is undefined.
- No-theme detection: all shade IDs contain `'00000000000'`.

## Naming model

Penpot stores local color styles with two separate fields:

| Field | Role | Example |
|---|---|---|
| `LibraryColor.path` | Folder hierarchy, ` / `-separated | `UICP Color Primitives / Light / Primary` |
| `LibraryColor.name` | Leaf name (shade) | `80` or `source` |

Resulting full display path (Penpot UI): `path / name`

- no themes: `paletteName / colorName / shadeName`
- with themes: `paletteName / themeName / colorName / shadeName`

Always set `path` and `name` independently — do not concatenate them. The `" / "` separator (with spaces) is what Penpot uses to build folder hierarchy; this differs from Figma which uses `"/"` without spaces.

## Workflow

1. Ensure a palette exists in the current Penpot plugin context.
2. Run local style sync for the selected/current palette.
3. Confirm the result in terms of:
   - styles created
   - styles updated
   - styles removed
4. If the user wants the semantic token layer as well, recommend using `ui-color-palette-penpot-generate-tokens` first or next.
5. If the user wants a visible palette board, route next to a document preview workflow.

## Tokens vs styles

Prefer this distinction:

- **Tokens**: semantic color system
- **Styles**: visual/application layer for local colors

If the user says only “Penpot tokens”, use the tokens skill first.
If the user says “styles”, “local colors”, or “swatches”, use this skill.

## When to use

Use this skill when the user asks for:

- Penpot styles
- Penpot local colors
- swatches in Penpot
- reusable local color styles
- color style library generation in Penpot

## Output

Report a concise sync summary, for example:

- styles created: `18`
- styles updated: `12`
- styles removed: `0`

Do not print the full palette payload.

## Tips

- Styles are for visual reuse, not the primary token graph.
- For theme-heavy systems, generate tokens first, then styles if the user also needs a style library.
- If the user wants an actual review artifact in the file, pair this with a document/board preview.
