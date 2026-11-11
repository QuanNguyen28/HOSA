---
name: ui-color-palette-penpot-generate-tokens
description: Generate or sync Penpot local tokens from a UI Color Palette, and optionally create a visual board/document preview. Use when the user wants a Penpot-native token workflow.
argument-hint: <palette-id|current-palette> [tokens|preview]
---

# Generate Penpot Tokens

Use this skill when the user wants a palette pushed into **Penpot local tokens**.

In Penpot, tokens are the main semantic representation for a palette. For UI Color Palette, this workflow can generate:

- local token sets
- local themes grouped by palette name
- one token per `color/shade`
- an optional board/document preview for visual review

## Source of truth

Treat **Penpot tokens** as the source of truth.

- Tokens represent color design tokens
- Sets represent palette or theme partitions
- Themes group themed token sets
- A board/document is only a visual artifact, not the token source

If the user asks for “Penpot tokens”, use this skill first.

## Structure-first execution

Use this file as a workflow specification, not as an API catalog.

Execution order:

1. identify the target artifact: token catalog first, preview second if requested
2. reduce the palette to the minimum token payload
3. apply token synchronization before any visual artifact
4. only then map the workflow to MCP or plugin API calls

The API layer is secondary to the workflow structure.

## Input contract

Before orchestration, the agent should ensure:

- a palette is already available in the active plugin or MCP context
- the target palette is selected explicitly or can be inferred as the current palette
- palette data includes stable theme, color, and shade naming
- each shade exposes `hex` and optional description
- the user intent is classified as token sync only or token sync plus preview

If one of these conditions is missing, resolve that upstream before token orchestration.

## Normalized PaletteData projection

Reduce `PaletteData` to two reusable row models before execution:

- `tokenRows`: `paletteName`, `themeName`, `colorName`, `shadeName`, `tokenSetName`, `tokenName`, `hex`, `description`
- `previewRows`: `paletteName`, `themeName`, `colorName`, `shadeName`, `displayLabel`, `hex`, `description`

> The `tokenRows` model has **one row per `(themeName, colorName, shadeName)` triplet**. Arc and dark themes produce independent `hex` values for every shade that differ from the light theme (arc themes invert the scale: shade `50` is darkest, shade `900` is lightest). Never merge, average, or deduplicate `hex` values across themes — each theme row is independent.

Token name encoding (exact logic from implementation):
1. Apply `doSnakeCase()` to `colorName` (e.g. `Primary Blue` → `primary_blue`; single-word names like `UICP` → `uicp`)
2. On each segment (`[colorNameSnake, shadeName]`), replace remaining spaces with `-`
3. Filter out empty strings and `'None'`
4. Join with `.` → `colorName_snake.shadeName`
5. Replace `・` with `_` on the resulting string
6. Fallback: if `colorName` is empty, use the localized default color name (snake-cased)

Examples:
- color `Primary Blue`, shade `500` → `primary_blue.500`
- color `UICP`, shade `80` → `uicp.80`
- color `Primary`, shade `source` → `primary.source`

The `"source"` shade (the reference/input color for each family) is **always included** as a token alongside the generated scale steps.

Set name encoding:
- **no themes**: one set named `palette.base.name` (falls back to localized default if empty)
- **with themes**: one set per theme named `palette.base.name/themeName` (theme name falls back to localized default if empty)

Token value: `shade.hex ?? '#000000'` (raw hex string; fallback to black if undefined)

These normalized row models are the actual handoff from palette structure to Penpot token and preview generation.

## Sync behaviour

- **No-theme palette**: one token set named `paletteName`. No-theme detection: all shade IDs contain `'00000000000'`.
- **Themed palette**: one token set per theme (`paletteName/themeName`, no spaces around `/`) + one theme entry per theme (`group: paletteName`, `name: themeName`).
- Includes the `"source"` shade for each color family alongside the numbered scale steps.
- Token names follow `colorName_snake.shadeName` encoding (see normalized projection above).
- **Token value**: for each themed set `paletteName/themeName`, use only the `tokenRows` where `themeName` matches the current set — use **that row's** `hex ?? '#000000'`. **Never reuse the light or base theme's `hex` for other sets** — arc and dark theme rows carry independently-computed hex values. Using the wrong row's `hex` for a set is the most common cause of inverted shades appearing identical across themes.
- **Newly created sets are inactive by default** (`active: false`) — call `set.toggleActive()` only if the user explicitly wants them applied to shapes.
- Deep sync: optionally remove orphan tokens, sets, and themes.
- Use `penpot_api_info` to look up `TokenCatalog`, `TokenSet`, `TokenTheme` API details at execution time.

## SystemData workflow

If `SystemData` is present in context, do not use this file.

Route to `references/generate-semantic-tokens.md` instead — it handles the full semantic token set workflow (reference string bindings, theme set naming, token path encoding).

This file covers **primitive** tokens only.

## Penpot mapping

| UI Color Palette data | Penpot target |
| --------------------- | ------------- |
| `palette.base.name` | Token set name (no themes) / set prefix + theme group name (with themes) |
| No-theme palette | Single set: `paletteName` |
| Themed palette | One set per theme: `paletteName/themeName` (no spaces around `/`) + one theme: `{ group: paletteName, name: themeName }` |
| `colorName` (snake_case, spaces → `-`) | First segment of token name (before `.`) |
| `shadeName` (including `"source"`) | Second segment of token name (after `.`) |
| `shade.hex` | Token value |
| `shade.description` | Token description |
| New token set | Created inactive (`active: false`) — toggle explicitly if needed |

## Workflow

1. Ensure a palette exists in the current Penpot plugin context.
2. Prefer the selected/current palette unless the user provides a palette ID.
3. Sync local tokens.
4. Confirm the result in terms of:
   - token sets created or reused
   - themes created, updated, or removed
   - tokens created, updated, or removed
5. If the user wants a visual deliverable, create or update a board/document preview after token sync.
6. If the user also wants reusable local color styles, route next to `ui-color-palette-penpot-generate-styles`.

## Visual preview option

If the user asks for a board, sheet, document, or palette preview in Penpot:

- sync tokens first
- then create or update a document preview

Preview expectations:

- one board/document per generated view
- grouped by theme
- grouped by color family
- visible shade swatches for review

## When to use

Use this skill when the user asks for:

- Penpot tokens
- Penpot color tokens
- token sets in Penpot
- theme tokens in Penpot
- full token sync in Penpot

## Output

Return a concise operational summary, for example:

- token sets: `2`
- themes: `+2`, `~1`, `-0`
- tokens: `+24`, `~24`, `-3`
- preview: created

Do not dump the full palette payload.

## Tips

- In Penpot, tokens should be preferred over styles for semantic design tokens.
- Theme-aware palettes should usually create themes and token sets before any visual board work.
- If the user wants a readable artifact for review, generate a board/document after syncing tokens.
- If strict cleanup is needed, ensure deep sync for tokens is enabled.
