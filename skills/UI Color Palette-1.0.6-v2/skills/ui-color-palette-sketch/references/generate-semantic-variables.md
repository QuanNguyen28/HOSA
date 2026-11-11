---
name: ui-color-palette-sketch-generate-semantic-variables
description: Generate or sync Sketch semantic swatches from SystemData. Use when the user wants token paths from a color system mapped as named swatches with resolved hex values, organized by taxonomy and theme.
argument-hint: <system-name> [sync]
---

# Generate Sketch Semantic Variables

Use this skill when the user wants to push a **semantic color system** (produced by `get_color_system` / `ui-color-palette-build-color-system`) into **Sketch document swatches** organized by token taxonomy.

Sketch has no alias or reference mechanism. Semantic swatches hold **raw hex values** resolved from the bound primitive shade. The token taxonomy (role, prominence, state…) is encoded directly in the swatch name path.

```
Swatch "MySystem/Light/Brand/Default"  →  hex: #3B82F6
Swatch "MySystem/Dark/Brand/Default"   →  hex: #93C5FD
```

Since Sketch has no mode concept, each theme produces its own swatch. Switching themes means changing which swatch group you apply manually.

---

## Prerequisites

**Primitive swatches must exist first.**

Semantic swatches in Sketch carry their own resolved hex — they do not reference primitives at runtime. However, the hex values are **resolved from the same PaletteData** used to generate the primitive swatches. If `PaletteData` is not in context, run `ui-color-palette-sketch-generate-variables` first to ensure consistency.

**Do not skip this check.** Before generating semantic swatches:

1. Verify that `PaletteData` is in context.
2. Verify that primitive swatches exist in the document (for consistency and cross-referencing).
3. If missing, run `ui-color-palette-sketch-generate-variables` first, then return here.

Confirm to the user before proceeding:

> Primitive swatches found. Ready to generate semantic swatches.

If not found:

> Primitive swatches are missing. Generating them now before proceeding with semantic swatches.

---

## Input contract

Before syncing, verify:

- `SystemData` is available in the conversation context (produced by `get_color_system`)
- `PaletteData` is available in context (needed to resolve `shadeId` → hex)
- A semantic swatch name prefix is known (from `SystemData.schema` or user-supplied label)

---

## Normalized SystemData projection

Reduce `SystemData` to a swatch-ready row model before execution:

- `systemName` — user-supplied label or derived from the system schema
- `tokenPath` — `token.pathNames.filter(n => n !== '' && n !== 'None').join('/')` (e.g. `Brand/Default`)
- `isExcluded` — skip the token if `true`
- Per-theme swatch, for each theme at index `i`:
  - `shadeId` — `token.refs[i].shadeId` (format: `themeId:colorId:shadeName`, or `null` if unbound)
  - `themeName` — the theme's display name (from the palette theme at index `i`)
  - `hex` — resolved from `shadeId` (see resolution below)
  - `swatchName` — full swatch path (see naming below)

### Hex resolution

Given a `shadeId` (format: `themeId:colorId:shadeName`):

1. Parse: extract `colorId` and `shadeName` (ignore `themeId`).
2. Find the color in `PaletteData` whose `id === colorId` → get `colorName`.
3. Find the shade in that color whose `name === shadeName` → get `shade.hex`.
4. Use `shade.hex` as the swatch color value.

There is no alias — the hex value is written directly into the swatch.

If the shade is not found, **skip that theme's swatch** and warn: `shadeId not resolved — shade missing for <colorId>:<shadeName>`.

### Swatch naming

Swatch names encode the full semantic path. Sketch uses `/` (no spaces) as a group separator:

- **No-theme system** (all shade IDs contain `'00000000000'`): `systemName/tokenPath`
  - e.g. `MySystem/Brand/Default`
- **Themed system**: `systemName/themeName/tokenPath`
  - e.g. `MySystem/Light/Brand/Default` and `MySystem/Dark/Brand/Default`

Empty segments are filtered out.

---

## Sync behaviour

- Deduplicates by swatch **name** — no id is persisted; swatches are matched by name on every sync.
- Creates missing swatches; updates the color of existing ones.
- **Skip** if `token.isExcluded === true`.
- **Skip** if `token.refs[i].shadeId === null` (unbound — no swatch created for that theme).
- No-theme detection: all shade IDs contain `'00000000000'`.
- Persists palette state to document settings and calls `Document.save()`.

---

## Sketch mapping

| `SystemData` / `PaletteData` field | Sketch target |
| ------------------------------------------- | ----------------------------------------------- |
| `systemName` (label or schema name) | Swatch name prefix |
| No-theme system | `systemName/tokenPath` |
| Themed system | `systemName/themeName/tokenPath` (one swatch per theme) |
| `token.pathNames.filter(…).join('/')` | Swatch name suffix (token path segments) |
| `token.refs[i].shadeId` → `shade.hex` | Swatch color (raw hex — no alias) |
| `token.isExcluded === true` | Token skipped entirely |
| `token.refs[i].shadeId === null` | Theme swatch skipped (unbound) |

---

## Workflow

1. Confirm `SystemData` and `PaletteData` are in context.
2. Confirm primitive swatches exist (or run `ui-color-palette-sketch-generate-variables` first).
3. For each non-excluded token, for each bound theme: resolve the hex and create or update the swatch.
4. Report the outcome (see Output section).
5. Ask what to do next:
   - **Generate styles** → `ui-color-palette-sketch-generate-styles`
   - **Preview on canvas** → `ui-color-palette-sketch-generate-preview`
   - **Adjust bindings** → re-run `ui-color-palette-build-color-system`, then re-sync here

---

## Output

Report a concise operational summary:

- swatches created: `18`
- swatches updated: `0`
- swatches removed: `2`
- unbound tokens skipped: `3`

Do not dump the full `SystemData` or `PaletteData` JSON.

---

## Tips

- Sketch swatches carry **raw hex values** — there is no alias or reference chain. If the primitive palette changes, semantic swatches must be re-synced manually.
- Each theme produces a separate swatch group (`systemName/Light/…`, `systemName/Dark/…`). Designers switch themes by applying the appropriate swatch group, not via a mode toggle.
- Because there is no runtime resolution, the semantic and primitive swatch groups can coexist in the same document without conflict.
- If strict cleanup is required, enable deep sync to remove orphan semantic swatches.
