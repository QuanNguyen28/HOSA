---
name: ui-color-palette-framer-generate-styles
description: Generate and update Framer local color styles from a UI Color Palette. Use when the user wants reusable Framer color styles created and kept in sync.
argument-hint: <palette-id|current-palette> [sync]
---

# Generate Framer Styles

Use this skill when the user wants a palette projected into **Framer color styles**.

In this plugin, the Framer integration supports a full `create + update` workflow for local color styles.

## Structure-first execution

Use this file as a workflow specification, not as an API catalog.

Execution order:

1. identify the target artifact: color styles
2. reduce the palette to the minimum style payload
3. apply the sync workflow
4. only then map the workflow to MCP or plugin API calls

The API layer is secondary to the workflow structure.

## Input contract

Before synchronization, the agent should ensure:

- a palette is already available in the active plugin or MCP context
- the target palette is selected explicitly or can be inferred as the current palette
- palette data includes stable palette, theme, color, and shade naming
- each shade exposes the color data needed to derive `light` and optional `dark` values

If one of these conditions is missing, resolve that upstream before style sync.

## Normalized PaletteData projection

Reduce `PaletteData` to a style-ready row model before execution:

- `paletteName`
- `themeName`
- `colorName`
- `shadeName`
- `shadeName` — includes `"source"` (the source/reference shade; its `dark` value equals `light`)
- `stylePath` (the `stylePath` field for `manageColorStyle`): **must start with `/"`** — `"/" + segments.join("/")`
  - no themes: `/paletteName/colorName/shadeName`
  - with themes: `/paletteName/themeName/colorName/shadeName` (theme name falls back to localized default if empty)
  - empty segments are filtered out
- `styleName` (display name, derived automatically from last path segment by Framer)
- `gl`: OpenGL-normalized RGB triple `[r, g, b]` in `[0, 1]` range
- `alpha`: opacity in `[0, 1]`
- `light`: `rgba(r255, g255, b255, a)` or `rgb(r255, g255, b255)` when `alpha === 1` — computed from `gl`
- `dark`: the mirror shade’s `rgba`/`rgb` string (see dark value logic below), falls back to `light` for the `source` shade

**Dark value logic** (computed per shade):
1. Collect all shades in the same theme + color family, excluding `source`.
2. Find the current shade’s index in that list.
3. Compute `oppositeIndex = totalShades - 1 - currentIndex`.
4. If a different shade exists at `oppositeIndex`, use its `gl` + `alpha` as the `dark` value.
5. If no opposite exists, or if `shadeName === 'source'`, use `light` as `dark`.

This normalized row model is the actual handoff from palette structure to Framer color style operations.

## Sync behaviour

- Check `framer.isAllowedTo('createColorStyle')` before any creation call.
- Find existing styles by stored `styleId`; create only when not found.
- Includes the `"source"` shade — its `dark` value always equals `light`.
- `stylePath` **must start with `/`** (e.g. `/UICP Color Primitives/Light/Primary/source`).
- `light` and `dark` values: `rgb(r, g, b)` or `rgba(r, g, b, a)` strings computed from `gl` + `alpha`.
- `dark` is computed from the mirror shade: `oppositeIndex = totalShades - 1 - currentIndex` (excluding `source`).
- No-theme detection: all shade IDs contain `'00000000000'`.
- Persists palette state to `window.localStorage`.

## Framer mapping

| UI Color Palette data | Framer target |
| --------------------- | ------------- |
| No-theme palette | `stylePath`: `/paletteName/colorName/shadeName` |
| Themed palette | `stylePath`: `/paletteName/themeName/colorName/shadeName` |
| `shade.gl` + `shade.alpha` | `light`: `rgb(r255, g255, b255)` or `rgba(r255, g255, b255, a)` |
| Mirror shade at `totalShades - 1 - index` | `dark` value (same rgb formula) |
| `source` shade (including `shadeName === "source"`) | `dark === light` |
| `framer.isAllowedTo('createColorStyle')` | Gate before any creation call |

## Important note

This Framer implementation does not expose a separate variables/tokens layer in the same way as Figma Variables or Penpot Tokens.

For Framer, the practical reusable color layer is **color styles**.

## SystemData workflow (semantic color styles)

When `SystemData` is present in the conversation context, use this section instead of the standard palette workflow above.

Framer color styles hold a `light` and a `dark` value. For a themed system, the first theme maps to `light` and the second to `dark`. For systems with more than 2 themes, warn the user that Framer only supports light/dark and use the first two themes only.

### Step 0 — ensure primitives exist

Semantic styles build on top of the primitive style set. Check that the palette's primitive styles already exist. If not, run the full primitive sync first — **mandatory**.

### Step 1 — semantic styles

Check `framer.isAllowedTo('createColorStyle')` before any creation call.

For each token in `SystemData.tokens`:

1. **Skip** if `token.isExcluded === true`.
2. Token path: `token.pathNames.filter(n => n !== '' && n !== 'None').join('/')`.
3. Build `stylePath`: `"/" + systemName + "/" + tokenPath` (e.g. `/MySystem/Brand/Default`).
4. Resolve `light` value:
   - From `token.refs[0]` (first theme). If `shadeId === null`, skip the style entirely.
   - Find the shade matching `ref.shadeId` in `PaletteData`, read `gl` + `alpha`.
   - Compute `rgb(r255, g255, b255)` or `rgba(r255, g255, b255, a)`.
5. Resolve `dark` value:
   - If only one theme: `dark === light`.
   - If two or more themes: from `token.refs[1]`. If `shadeId === null`, fall back to `light`.
   - If three or more themes: warn and ignore themes beyond the second.
6. Create or update the color style with `stylePath`, `light`, and `dark`.

### SystemData Framer mapping

| `SystemData` field | Framer target |
| ------------------------------------------ | -------------------------------------------- |
| Schema name or user label | `stylePath` prefix (`/systemName/…`) |
| `token.pathNames.filter(...).join('/')` | `stylePath` suffix (token path segments) |
| `token.refs[0].shadeId` → shade `gl` | `light` value (`rgb` / `rgba` string) |
| `token.refs[1].shadeId` → shade `gl` | `dark` value (`rgb` / `rgba` string) |
| Single theme or no-theme | `dark === light` |
| 3+ themes | Warn user; only first two themes used |
| `token.isExcluded === true` | Skip token entirely |
| `token.refs[0].shadeId === null` | Skip this token (no light value) |
| `token.refs[1].shadeId === null` | Fall back to `light` for dark value |

## Workflow

1. Ensure the palette exists in the current Framer plugin state.
2. Prefer the selected/current palette unless the user specifies a palette ID.
3. Run the Framer style sync workflow.
4. Always think of the sync as `create + update`, not only creation.
5. Confirm the result in terms of:
   - styles created
   - styles updated
   - styles removed
6. If the user also wants a visible artifact, route next to document preview generation.

## When to use

Use this skill when the user asks for:

- Framer color styles
- local styles in Framer
- reusable palette styles
- keep Framer styles in sync
- generate and update styles in Framer

## Output

Return a concise sync summary, for example:

- styles created: `18`
- styles updated: `12`
- styles removed: `2`

Do not dump the full palette payload.

## Tips

- For Framer, styles are the main reusable color artifact.
- Always include the update step after creation when the intent is synchronization.
- If the user wants a visual review artifact, pair style sync with document preview generation.
- If deep cleanup is required, ensure deep sync for styles is enabled.
