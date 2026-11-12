---
name: ui-color-palette-figma-generate-styles
description: Generate or sync Figma local paint styles from a UI Color Palette. Use when the user wants swatches or reusable paint styles created from the palette in Figma.
argument-hint: <palette-id|current-palette> [sync]
---

# Generate Figma Styles

Use this skill when the user wants a palette projected into **Figma local paint styles**.

Styles are useful for:

- visual swatch libraries
- fill style reuse in mockups
- quick inspection of palette output inside Figma
- compatibility with legacy style-based workflows

## Structure-first execution

Use this file as a workflow specification, not as an API catalog.

Execution order:

1. identify the target artifact: styles
2. reduce the palette to the minimum style payload
3. apply the sync workflow
4. only then map the workflow to MCP or plugin API calls

The API layer is secondary to the workflow structure.

## Input contract

Before synchronization, the agent should ensure:

- a palette is already available in the active plugin or MCP context
- the target palette is selected explicitly or can be inferred as the current palette
- palette data includes stable palette, theme, color, and shade naming
- each shade exposes RGBA plus optional description

If one of these conditions is missing, resolve that upstream before style sync.

## Normalized PaletteData projection

Reduce `PaletteData` to a style-ready row model before execution:

- `paletteName`
- `themeName`
- `colorName`
- `shadeName` — includes `"source"` (the source/reference shade for each color family)
- `styleName` (full Figma style path, used as both path and name): `paletteName/colorName/shadeName` (no themes) or `paletteName/themeName/colorName/shadeName` (with themes) — empty segments filtered out
- `gl`: OpenGL-normalized RGB triple `[r, g, b]` in `[0, 1]` range — taken from **that theme's** `shade.gl`, not from the base or first theme
- `alpha`: opacity in `[0, 1]`
- `description`

> The row model has **one row per `(themeName, colorName, shadeName)` triplet**. Arc and dark themes produce independent `gl` values for every shade. Never reuse the base or light theme's `gl` for a dark/arc theme's row — each row carries the independently-computed color for that theme.

This normalized row model is the actual handoff from palette structure to Figma paint style operations.

## Sync behaviour

- Creates missing paint styles; finds existing ones by stored `styleId` before creating.
- Includes the `"source"` shade for each color family alongside the numbered scale steps.
- Style name is the full path as a **single string** — Figma parses `/` (no spaces) as group separator.
- Fill set from `gl` (OpenGL-normalized RGB) + `alpha` — use **the row's own `gl`** (the one where `themeName` matches the style's theme path segment). **Never reuse the base or light theme's `gl`** for a dark/arc themed style; arc theme rows already carry the inverted hex values. Skips shades where `gl` is undefined.
- No-theme detection: all shade IDs contain `'00000000000'`.
- Optionally removes orphan styles when deep sync is enabled.

## Naming model

Figma interprets `/` in a paint style name as a group separator. The full style path is set as a single `style.name` string:

- no themes: `paletteName/colorName/shadeName`
- with themes: `paletteName/themeName/colorName/shadeName`

## Workflow

1. Ensure a palette exists in the current Figma plugin context.
2. Run local style sync for the selected/current palette.
3. Confirm the result in terms of:
   - styles created
   - styles updated
   - styles removed
4. If the user wants tokens as the main system, recommend generating variables as well.
5. If the user wants a visible board or sheet, route next to `CREATE_DOCUMENT`.

## When to use

Use this skill when the user asks for:

- Figma styles
- local paint styles
- palette swatches in Figma
- reusable fills from the palette
- color style library generation

## Variables vs styles

Prefer this distinction:

- **Variables**: token system and theme logic
- **Styles**: visual/application layer for fills

If the user says only “tokens”, use the variables skill first.
If the user says “I want swatches/styles in Figma”, use this skill.

## Output

Report a concise sync summary, for example:

- styles created: `18`
- styles updated: `12`
- styles removed: `0`

Do not print the full palette payload.

## Tips

- Styles are best for visual reuse, not as the primary token graph.
- Theme-heavy systems should usually generate variables first, then styles if needed.
- If the user wants to inspect the palette visually, pair this with a document preview.
