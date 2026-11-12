---
name: ui-color-palette-sketch-generate-styles
description: Generate or sync Sketch shared layer styles from a UI Color Palette. Use when the user wants reusable local styles from the palette in Sketch.
argument-hint: <palette-id|current-palette> [sync]
---

# Generate Sketch Styles

Use this skill when the user wants a palette projected into **Sketch shared layer styles**.

Styles are useful for:

- reusable fills in mockups
- visual swatch/style libraries
- design review from applied color styles
- bridging palette data into existing Sketch style workflows

## Structure-first execution

Use this file as a workflow specification, not as an API catalog.

Execution order:

1. identify the target artifact: shared styles
2. reduce the palette to the minimum style payload
3. apply the sync workflow
4. only then map the workflow to MCP or plugin API calls

The API layer is secondary to the workflow structure.

## Input contract

Before synchronization, the agent should ensure:

- a palette is already available in the active plugin or MCP context
- the target palette is selected explicitly or can be inferred as the current palette
- palette data includes stable palette, theme, color, and shade naming
- each shade exposes a usable `hex` value

If one of these conditions is missing, resolve that upstream before style sync.

## Normalized PaletteData projection

Reduce `PaletteData` to a style-ready row model before execution:

- `paletteName`
- `themeName`
- `colorName`
- `shadeName` — includes `"source"` (the source/reference shade for each color family)
- `styleName` (full path, used as the single `name` field): segments joined with `/` (no spaces)
  - no themes: `paletteName/colorName/shadeName`
  - with themes: `paletteName/themeName/colorName/shadeName` (theme name falls back to localized default if empty)
  - empty segments are filtered out
- `hex`: raw hex string from `shade.hex` (Sketch API returns/accepts `#rrggbbff` format with alpha suffix)

> Note: Sketch styles have no separate `alpha` field — only `hex` is used. This differs from Figma (GL + alpha) and Penpot (hex + alpha).

This normalized row model is the actual handoff from palette structure to Sketch shared style operations.

## Sync behaviour

- Creates missing shared layer styles; finds existing ones by stored `styleId` before creating.
- Includes the `"source"` shade for each color family alongside the numbered scale steps.
- Style name is the full path as a **single string** — Sketch parses `/` (no spaces) as group separator.
- Fill color set from `hex` only (no separate alpha field — Sketch styles have no opacity layer).
- No-theme detection: all shade IDs contain `'00000000000'`.
- Persists palette state to document settings and calls `Document.save()`.

## Sketch mapping

| UI Color Palette data | Sketch target |
| --------------------- | ------------- |
| No-theme palette | `paletteName/colorName/shadeName` as shared style name |
| Themed palette | `paletteName/themeName/colorName/shadeName` as shared style name |
| `shade.hex` | Style fill color (no alpha channel) |

## Workflow

1. Ensure a palette exists in the current Sketch document plugin state.
2. Run local style sync for the selected/current palette.
3. Confirm the result in terms of:
   - styles created
   - styles updated
   - styles removed
4. If the user wants the variable/swatch layer too, recommend using `ui-color-palette-sketch-generate-variables` first or next.
5. If the user wants a visible board or sheet, route next to document preview.

## Variables vs styles

Prefer this distinction:

- **Variables / swatches**: color source layer in this plugin
- **Styles**: reusable application layer for Sketch design surfaces

If the user says only “tokens” or “variables”, use the variables skill first.
If the user says “styles” or “shared styles”, use this skill.

## When to use

Use this skill when the user asks for:

- Sketch styles
- shared layer styles
- palette styles in Sketch
- reusable color styles

## Output

Report a concise sync summary, for example:

- styles created: `18`
- styles updated: `12`
- styles removed: `0`

Do not print the full palette payload.

## Tips

- Styles are the visual/application layer, not the main semantic token graph.
- If the user wants both maintainability and visual reuse, generate swatches first, then styles.
- Pair this with a document preview when the user wants an immediately reviewable artifact.
