---
name: ui-color-palette-build-color-system
description: Define a semantic color system taxonomy and resolve bindings against a palette using get_color_system. Use when the user wants to map semantic token names (role, prominence, state…) to primitive color shades. Produces a SystemData object for use in semantic code generation or design tool deployment.
argument-hint: <schema-description>
---

# Build Color System

Use the **ui-color-palette** MCP tool `get_color_system` to resolve a semantic token taxonomy against a generated palette and produce a `SystemData` object.

Semantic code export from the system is handled by `ui-color-palette-generate-semantic-code`.

---

## Pre-flight — Check session state

Before asking any questions, check the conversation context for existing slots.

### If `SystemData` is already in context

Show a summary (token count, bound / unbound / excluded). Ask: reuse, rebuild, or adjust bindings.

### If `SystemConfiguration` is already in context

Skip Step 0. Call `get_color_system` directly with the existing `base`, `themes`, and `system` values.

### If `PaletteData` or `base` + `themes` are already in context

Skip the palette questions in Step 0.

---

## Step 0 — Gather parameters

Do not call the tool until all required answers are collected.

### Required

**1. Palette inputs** — confirm `base` and `themes` are available. If not, run `ui-color-palette-scale-palette` first.

**2. Taxonomy groups** — ask for the semantic dimensions that structure the token names.

Each group has an `id`, a `name`, and `members` (each with `id` and `name`). The system generates the **cartesian product** of all groups: 2 groups × 3 members each = 6 tokens; 3 groups × 3 members = 27 tokens.

Common patterns:

| Pattern | Groups | Typical members |
| ------- | ------ | --------------- |
| Role × State | `role`, `state` | brand / neutral / danger ; default / hover / active / disabled |
| Role × Prominence × State | `role`, `prominence`, `state` | — ; default / subtle / strong ; — |
| Surface × Content | `surface`, `content` | background / border ; primary / secondary / inverse |

**3. Theme strategy** — before defining bindings, confirm which strategy the user wants:

| Strategy | Description | `overrides` in bindings |
| -------- | ----------- | ----------------------- |
| **A — Primitive modes** *(recommended)* | Themes handled at the primitive level. Semantic tokens use a single binding. `get_palette` already carries the correct per-theme values at each shade stop. | Almost never — only for deliberate per-theme shade deviations |
| **B — Semantic modes** | Themes handled at the semantic level. Each token has an explicit binding per theme via `overrides`. Semantic variable collection has one mode per theme. | Expected on most tokens that differ across themes |

Record the strategy before defining bindings. It determines the binding format and how the semantic collection will be structured in design tools.

**4. Bindings** (iterative — start with the most important ones) — map token paths to primitive shade refs.

Format: `[memberId, memberId, …] → colorId:shadeName` (e.g. `[brand, default] → blue:500`).

Optional per-binding fields:

| Field | Description |
| ----- | ----------- |
| `description` | Optional label for the token |
| `overrides` | Per-theme alternative ref: `{ themeId: "colorId:shadeName" }` — use for Strategy B, or for deliberate deviations in Strategy A |
| `isExcluded` | `true` → token stays in SystemData but is skipped during code generation |

---

## Step 1 — Call `get_color_system`

**Tool**: `get_color_system`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `base` | object | Yes | `BaseConfiguration` — same schema as `get_palette` |
| `themes` | array | Yes | Array of `ThemeConfiguration` objects |
| `system` | object | Yes | `SystemConfiguration` — schema + optional bindings |

### `system.schema`

| Field | Type | Description |
| ----- | ---- | ----------- |
| `groups` | array | Ordered list of taxonomy groups (order defines the path depth) |

Each group:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Group identifier (e.g. `"role"`) |
| `name` | string | Display name (e.g. `"Role"`) |
| `members` | array | List of `{ id: string, name: string }` |

### `system.bindings` (optional)

Each binding:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `path` | `string[]` | Ordered member ids (one per group), e.g. `["brand", "default"]` |
| `description` | string | Optional token description |
| `ref` | string | Default primitive ref: `"colorId:shadeName"` (e.g. `"blue:500"`) |
| `overrides` | `Record<string, string>` | Per-theme overrides: `{ themeId: "colorId:shadeName" }` |
| `isExcluded` | boolean | `true` → present in SystemData, excluded from code generation |

**Returns**: a `SystemData` object with `schema`, `tokens`, and `type: "system"`.

Each token in `tokens`:

| Field | Description |
| ----- | ----------- |
| `path` | Member id path (e.g. `["brand", "default"]`) |
| `pathNames` | Display name path (e.g. `["Brand", "Default"]`) |
| `description` | Optional description from the binding |
| `isExcluded` | Whether excluded from code generation |
| `refs` | `{ themeId, shadeId }[]` — `shadeId` is `"themeId:colorId:shadeName"` or `null` if unbound |

---

## Step 2 — Display the token matrix

After calling `get_color_system`, produce a readable token matrix. **Do not display raw `SystemData` JSON.** Store the raw response opaquely as the `SystemData` slot — never read, print, or reason from the raw object. The only purpose of `SystemData` is to be passed as-is to downstream tools (semantic code generation, design tool deployment).

Format — one row per token, one column per theme:

```text
Token                           | Light              | Dark
--------------------------------|--------------------|--------------------
brand / default                 | blue:500           | blue:400
brand / subtle                  | blue:200           | blue:700
neutral / default               | slate:600          | slate:300
neutral / subtle                | — unbound —        | — unbound —
neutral / disabled   [excluded] | —                  | —
```

Legend:
- `colorId:shadeName` → resolved ref for this theme
- `— unbound —` → no binding or ref not found in palette
- `[excluded]` → binding has `isExcluded: true`

Finish with a one-line summary: e.g. `12 tokens — 9 bound, 2 unbound, 1 excluded`.

---

## Workflow

1. Confirm `base` and `themes` are available (from context or `ui-color-palette-scale-palette`).
2. Gather taxonomy groups and members from the user.
3. **Choose theme strategy** — ask before defining bindings:
   - **Strategy A — Primitive modes**: single binding per token, no overrides. `get_palette` carries per-theme values at the primitive level.
   - **Strategy B — Semantic modes**: explicit `overrides` per theme. Semantic collection has one mode per theme in the design tool.
4. Gather bindings (iterative — start with a subset, refine after preview).
5. Call `get_color_system`.
6. **Session state**: store result as `SystemData` slot, store the input `system` config as `SystemConfiguration` slot. Also record the chosen strategy (A or B) — it is needed by deploy steps.
7. Display the token matrix.
8. Ask what to do next:
   - **Adjust bindings** — add, change, or exclude specific tokens, then rebuild
   - **Generate semantic code** → `ui-color-palette-generate-semantic-code`
   - **Export to Figma as a semantic variable collection** → `ui-color-palette-figma` — pass strategy: A = single flat mode on the semantic collection; B = one mode per theme on the semantic collection.
   - **Export to Penpot as semantic token sets** → `ui-color-palette-penpot` — pass strategy: A = single flat set (`systemName`); B = one set per theme (`systemName/themeName`).
   - **Export to Sketch as semantic swatches** → `ui-color-palette-sketch` — one swatch per theme per token, names encode `systemName/themeName/tokenPath`.
   - **Export to Framer as semantic color styles** → `ui-color-palette-framer` — first theme maps to `light`, second to `dark`.

---

## Arguments

`$ARGUMENTS` can describe the taxonomy structure or the project context.

- `/ui-color-palette:build-color-system role × state for a design system`
- `/ui-color-palette:build-color-system brand + neutral × prominence × interaction`

## Tips

- **ref format**: `colorId` is the color's `id` field from `PaletteData`, **not** its display name.
- **partial bindings are fine**: unbound tokens appear in SystemData with `shadeId: null`. They show as `— unbound —` in the matrix.
- **isExcluded vs unbound**: `isExcluded` is an explicit design decision (token exists but is intentionally disabled); unbound is a missing binding.
- **overrides vs primitive cascade**: `get_palette` resolves all theme variations at the primitive level — the same shade ref is correct for all themes. Do not add shade-index overrides unless a token intentionally requires a different shade index in a specific theme.
- **source of truth for shade stops and color ids**: always read from the primitive palette (`PaletteData` or `base` config). Never assume shade names.

---

## Recommended subagents

- **`palette-color-systemer`** — guided color system design: pattern suggestion, intelligent binding proposals, iterative refinement, `get_color_system` submission. Use this instead of running the skill manually when the user needs step-by-step guidance.
- **`uicper`** — orchestrates the full source → palette → system → deploy workflow
- **`palette-codegen`** — generates semantic code files from `base` + `themes` + `system`
