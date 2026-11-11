---
name: ui-color-palette-figma-generate-semantic-variables
description: Generate or sync a Figma semantic variable collection from SystemData. Use when the user wants token paths from a color system mapped as VariableAlias references inside a dedicated Figma variable collection, with one mode per theme.
argument-hint: <system-name> [sync]
---

# Generate Figma Semantic Variables

Use this skill when the user wants to push a **semantic color system** (produced by `get_color_system` / `ui-color-palette-build-color-system`) into **Figma local variables** as a dedicated semantic collection.

Semantic variables are **always aliases** — they never hold a raw color value. Every mode value is a `VariableAlias` pointing to a primitive variable. Figma resolves the actual color at render time based on the current mode context.

```
Layer uses semantic "Brand/Default"
  → Light mode → VariableAlias → primitive "blue/500" → Light mode value: #3B82F6
  → Dark mode  → VariableAlias → primitive "blue/300" → Dark mode value:  #93C5FD
```

This alias chain is what enables theme switching: switching modes on the semantic collection automatically re-resolves every alias.

---

## Prerequisites

**Primitive collection must exist first.**

Semantic variables reference primitive variables via `VariableAlias`. If the primitive collection for this palette has not yet been created, run `ui-color-palette-figma-generate-variables` first — then return here.

Confirm to the user before proceeding:

> Primitive collection found. Ready to generate semantic variables.

If not found:

> The primitive variable collection is missing. Running primitive sync first.

---

## Input contract

Before calling any API, verify:

- `SystemData` is available in the conversation context (produced by `get_color_system`)
- `PaletteData` is available in context (needed to resolve `shadeId` → primitive variable)
- The primitive Figma variable collection exists and can be referenced by its stored `collectionId`
- A semantic collection name is known (from `SystemData.schema` or user-supplied label)

---

## Normalized SystemData projection

Reduce `SystemData` to a semantic-variable-ready row model before execution:

- `systemName` — user-supplied label or derived from the system schema
- `tokenPath` — `token.pathNames.filter(n => n !== '' && n !== 'None').join('/')` (e.g. `Brand/Default`)
- `variableName` — `tokenPath` (same value; used directly as the Figma variable name)
- `description` — `token.description` if defined
- `isExcluded` — skip the token if `true`
- Per-mode alias, for each theme at index `i`:
  - `shadeId` — `token.refs[i].shadeId` (a string like `themeId:colorId:shadeName`, or `null` if unbound)
  - `primitiveVariableId` — resolved from `shadeId` by looking up the primitive variable whose path matches the shade (see resolution below)

### Primitive variable resolution

Each mode value in the semantic collection must be a `VariableAlias`. Never fall back to a raw RGB value — if the alias target cannot be resolved, skip that mode and warn.

Given a `shadeId` (format: `themeId:colorId:shadeName`):

1. Parse: extract `colorId` and `shadeName` (ignore `themeId` — it identifies the context, not the target).
2. Find the color in `PaletteData` whose `id === colorId` → get `colorName`.
3. Build the primitive variable name: `colorName/shadeName`.
4. Find the Figma variable in the primitive collection with that name → get its `id`.
5. Set the mode value: `variable.setValueForMode(modeId, { type: 'VARIABLE_ALIAS', id: primitiveVariable.id })`.

> Each mode of the semantic variable may alias to a **different** primitive variable (e.g. Light mode → `blue/500`, Dark mode → `blue/300`). This is intentional — `refs[i]` carries the shade appropriate for that theme.

If the primitive variable is not found, **skip that mode's value** and warn: `shadeId not resolved — primitive variable missing for <colorId>:<shadeName>`.

---

## Sync behaviour

### Collection

- One collection named `systemName`.
- Find by stored semantic `collectionId`; create if absent.
- Do **not** reuse the primitive collection — semantic variables live in their own collection.

### Modes

**Before setting up modes, ask the user:**

> The primitive collection already has one mode per theme. For the **semantic** collection, do you want:
> - **One mode per theme** *(recommended)* — mirrors the primitive structure; consumers can switch modes on the semantic collection to adapt all aliases at once
> - **Single mode** — flat semantic layer; theme adaptation relies entirely on the primitive collection; simpler but consumers cannot switch themes via the semantic collection alone

Depending on the answer:

**One mode per theme:**
- **No-theme system** (all shade IDs contain `'00000000000'`): single default mode, left as `'Mode 1'`.
- **Themed system**: rename the default mode to the first theme name; `collection.addMode(themeName)` for each subsequent theme. Each mode's alias target is resolved from `token.refs[i].shadeId` at the matching theme index.
- Track each `modeId` in theme order — must match `token.refs` index order.
- Warn and stop if `addMode` throws (Figma plan limit).

**Single mode:**
- Always use one mode (the default, `'Mode 1'`), regardless of how many themes the palette has.
- For each token, use `token.refs[0].shadeId` (the first/default theme ref) to resolve the alias.
- Do **not** call `addMode` — only the default mode exists.
- Note to user: theme switching on this semantic collection is not available; it is handled at the primitive level.

### Variables

For each token in `SystemData.tokens`:

1. **Skip** if `token.isExcluded === true`.
2. Variable name: `variableName` (the `/`-joined path).
3. Variable type: `COLOR`.
4. For each mode at theme index `i`:
   - **Skip this mode** if `token.refs[i].shadeId === null` (unbound — leave mode value unset).
   - Resolve `primitiveVariableId` (see Primitive variable resolution above). Skip with warning if not found.
   - **Set alias**: `variable.setValueForMode(modeId, { type: 'VARIABLE_ALIAS', id: primitiveVariableId })`.
   - Never write an RGB value here — the value must always be an alias.
5. Set `variable.description` from `token.description` if defined.

### Deep sync (optional)

When enabled: remove semantic variables that no longer correspond to a token in `SystemData`, and remove modes that no longer match a theme.

---

## Figma mapping

| `SystemData` / `PaletteData` field | Figma target |
| ------------------------------------------- | ---------------------------------------------- |
| `systemName` (label or schema name) | Semantic variable collection name |
| `token.pathNames.filter(…).join('/')` | Semantic variable name |
| One mode per theme *(if chosen)* | One collection mode per theme |
| Single mode *(if chosen)* | Default mode only (`'Mode 1'`) |
| `token.refs[i].shadeId` → primitive var id | `{ type: 'VARIABLE_ALIAS', id: … }` per mode |
| `token.refs[0].shadeId` *(single mode)* | Alias for the default mode only |
| `token.isExcluded === true` | Token skipped entirely |
| `token.refs[i].shadeId === null` | Mode value left unset (unbound) |
| `token.description` | Variable description |

---

## Workflow

1. Confirm `SystemData` and `PaletteData` are in context.
2. Confirm the primitive collection exists (or run `ui-color-palette-figma-generate-variables` first).
3. **Ask the user which mode strategy to use** (one mode per theme vs. single mode) — see Modes section above.
4. Resolve or create the semantic collection.
5. Set up modes according to the chosen strategy.
6. For each non-excluded token: create the variable and bind each mode to the corresponding primitive via `VariableAlias`.
7. Report the outcome (see Output section).
8. Ask what to do next:
   - **Generate styles** → `ui-color-palette-figma-generate-styles`
   - **Preview on canvas** → `ui-color-palette-figma-generate-preview`
   - **Adjust bindings** → re-run `ui-color-palette-build-color-system`, then re-sync here

---

## Output

Report a concise operational summary:

- collection: created or reused
- modes: `+2`, `~1`, `-0`
- variables: `+18`, `~0`, `-2`
- unbound tokens skipped: `3`

Do not dump the full `SystemData` or `PaletteData` JSON.

---

## Tips

- Semantic variables must live in a **separate collection** from the primitives — do not add them to the primitive collection.
- **Never set raw RGB values** on a semantic variable — the value type is always `VARIABLE_ALIAS`.
- A `VariableAlias` is set per mode individually — each mode can alias to a different primitive variable.
- Figma resolves the alias at render time using the current mode context, so the consumer (layer) automatically gets the right theme color.
- If a token has no binding for a given theme, leave that mode value unset (Figma tolerates unset mode values).
- If the primitive collection was renamed or rebuilt, primitive variable IDs may be stale — re-resolve by name from the current collection state.
- When the user wants to rename the semantic collection, update `systemName` and re-sync.
