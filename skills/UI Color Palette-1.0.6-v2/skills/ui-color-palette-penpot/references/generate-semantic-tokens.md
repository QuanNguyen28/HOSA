---
name: ui-color-palette-penpot-generate-semantic-tokens
description: Generate or sync Penpot semantic tokens from SystemData. Use when the user wants token paths from a color system mapped as reference values inside dedicated Penpot token sets, with one set per theme.
argument-hint: <system-name> [sync]
---

# Generate Penpot Semantic Tokens

Use this skill when the user wants to push a **semantic color system** (produced by `get_color_system` / `ui-color-palette-build-color-system`) into **Penpot local tokens** as dedicated semantic token sets.

Semantic tokens are **always references** — they never hold a raw hex value. Every token value is a `{primitiveTokenName}` reference string pointing to a primitive token. Penpot resolves the actual color at apply time based on the active theme.

```
Shape uses semantic "brand.default"
  → Light set  →  {blue.500}  →  primitive blue.500 value: #3B82F6
  → Dark set   →  {blue.300}  →  primitive blue.300 value: #93C5FD
```

Switching the active Penpot theme (Light → Dark) re-resolves every reference automatically.

---

## Prerequisites

**Primitive token sets must exist first — this is a hard requirement.**

Semantic token values are `{primitiveTokenName}` reference strings. If the primitive set does not contain the referenced token, Penpot will treat the reference as unresolved and the token will have no usable value.

**Do not skip this check.** Before generating any semantic token:

1. Verify that the primitive sets exist (`paletteName` or `paletteName/themeName`).
2. If they are missing or incomplete, run `ui-color-palette-penpot-generate-tokens` first, then re-enter this workflow.

Confirm to the user before proceeding:

> Primitive token sets found. Ready to generate semantic tokens.

If not found:

> Primitive token sets are missing. Generating them now before proceeding with semantic tokens.

---

## Input contract

Before calling any API, verify:

- `SystemData` is available in the conversation context (produced by `get_color_system`)
- `PaletteData` is available in context (needed to resolve `shadeId` → primitive token name)
- The primitive Penpot token sets exist (`paletteName` or `paletteName/themeName`)
- A semantic set name is known (from `SystemData.schema` or user-supplied label)

---

## Normalized SystemData projection

Reduce `SystemData` to a semantic-token-ready row model before execution:

- `systemName` — user-supplied label or derived from the system schema
- `tokenPath` — `token.pathNames.filter(n => n !== '' && n !== 'None').join('.')` (e.g. `brand.default`)
- `tokenName` — `tokenPath` (same value; used directly as the Penpot token name)
- `description` — `token.description` if defined
- `isExcluded` — skip the token if `true`
- Per-theme reference, for each theme at index `i`:
  - `shadeId` — `token.refs[i].shadeId` (a string like `themeId:colorId:shadeName`, or `null` if unbound)
  - `primitiveTokenName` — resolved from `shadeId` by encoding the matching shade (see resolution below)

### Primitive token name resolution

Each semantic token value must be a `{reference}` string — never a raw hex. If the reference cannot be resolved, skip that theme's value and warn.

Given a `shadeId` (format: `themeId:colorId:shadeName`):

1. Parse: extract `colorId` and `shadeName` (ignore `themeId` — it identifies the context, not the target).
2. Find the color in `PaletteData` whose `id === colorId` → get `colorName`.
3. Encode the primitive token name using the same logic as `ui-color-palette-penpot-generate-tokens`:
   - Apply `doSnakeCase()` to `colorName` (e.g. `Primary Blue` → `primary_blue`)
   - Replace remaining spaces with `-` in each segment
   - Filter empty strings and `'None'`
   - Join with `.` → `colorName_snake.shadeName`
   - Replace `・` with `_`
4. Wrap in curly braces: `{colorName_snake.shadeName}` — this is the token value written to the set.

> Each theme's set may reference a **different** primitive token (e.g. Light set → `{blue.500}`, Dark set → `{blue.300}`). This is intentional — `refs[i]` carries the shade appropriate for that theme.

If the primitive token is not found in the set, **skip that theme's value** and warn: `shadeId not resolved — primitive token missing for <colorId>:<shadeName>`.

---

## Sync behaviour

### Token sets

**Before setting up token sets, ask the user:**

> The primitive layer already has one set per theme. For the **semantic** layer, do you want:
> - **One set per theme** *(recommended)* — `systemName/themeName` per theme; switching the active Penpot theme adapts all references at once
> - **Single set** — one flat `systemName` set; theme adaptation relies entirely on the primitive layer; simpler but consumers cannot switch themes via the semantic sets alone

Depending on the answer:

**One set per theme:**
- **No-theme system** (all shade IDs contain `'00000000000'`): one set named `systemName`.
- **Themed system**: one set per theme named `systemName/themeName` (no spaces around `/`). Each set's token value is resolved from `token.refs[i].shadeId` at the matching theme index.
- Find existing sets by name; create if absent.
- Do **not** reuse the primitive sets — semantic tokens live in their own sets.

**Single set:**
- Always create one set named `systemName`, regardless of how many themes the palette has.
- For each token, use `token.refs[0].shadeId` (the first/default theme ref) to build the reference string.
- Do **not** create per-theme sets.
- Note to user: theme switching on this semantic layer is not available; it is handled at the primitive level.

### Token themes

- **One set per theme (themed system)**: one theme entry per theme (`group: systemName`, `name: themeName`). Find existing themes by group + name; create if absent.
- **Single set**: no theme entries created — the single set is used directly.

### Tokens

For each token in `SystemData.tokens`:

1. **Skip** if `token.isExcluded === true`.
2. Token name: `tokenName` (the `.`-joined path).
3. Token type: `color`.
4. For each theme at index `i`:
   - **Skip this set** if `token.refs[i].shadeId === null` (unbound — no token written for this theme).
   - Resolve `primitiveTokenName` (see Primitive token name resolution above). Skip with warning if not found.
   - Token value in set `systemName/themeName`: `{primitiveTokenName}` (reference string with curly braces — **never a raw hex value**).
5. Set token description from `token.description` if defined.
6. Newly created sets are **inactive by default** (`active: false`) — only toggle if the user explicitly asks.

### Deep sync (optional)

When enabled: remove semantic tokens that no longer correspond to a token in `SystemData`, and remove sets/themes that no longer match.

---

## Penpot mapping

| `SystemData` / `PaletteData` field | Penpot target |
| ------------------------------------------- | ----------------------------------------------------------- |
| `systemName` (label or schema name) | Semantic set name prefix |
| No-theme system | One set: `systemName` |
| Themed system — one set per theme *(if chosen)* | One set per theme: `systemName/themeName` + theme entry |
| Themed system — single set *(if chosen)* | One set: `systemName` (default theme refs used) |
| `token.pathNames.filter(…).join('.')` | Semantic token name |
| `token.refs[i].shadeId` → primitive name | Token value: `{colorName_snake.shadeName}` (reference string) |
| `token.refs[0].shadeId` *(single set)* | Token value using default theme ref only |
| `token.isExcluded === true` | Token skipped entirely |
| `token.refs[i].shadeId === null` | Theme set value omitted (unbound) |
| `token.description` | Token description |
| New token set | Created inactive (`active: false`) |

---

## Workflow

1. Confirm `SystemData` and `PaletteData` are in context.
2. Confirm the primitive token sets exist (or run `ui-color-palette-penpot-generate-tokens` first).
3. **Ask the user which set strategy to use** (one set per theme vs. single set) — see Token sets section above.
4. Resolve or create the semantic token set(s) and, if applicable, the theme group.
5. For each non-excluded token: create the token in the appropriate set(s) with the reference string value.
6. Report the outcome (see Output section).
7. Ask what to do next:
   - **Generate styles** → `ui-color-palette-penpot-generate-styles`
   - **Preview on canvas** → `ui-color-palette-penpot-generate-preview`
   - **Adjust bindings** → re-run `ui-color-palette-build-color-system`, then re-sync here

---

## Output

Report a concise operational summary:

- token sets: `2` (created or reused)
- themes: `+2`, `~0`, `-0`
- tokens: `+18`, `~0`, `-2`
- unbound tokens skipped: `3`

Do not dump the full `SystemData` or `PaletteData` JSON.

---

## Tips

- Semantic tokens must live in **separate sets** from the primitives — do not add them to the primitive sets.
- **Never write a raw hex value** — the token value must always be `{primitiveTokenName}` (reference string with curly braces).
- The `{reference}` encoding must exactly match the primitive token name character-for-character, including the snake_case encoding of the color name.
- Each theme's set can reference a different primitive token — this is how dark/light adaptation is expressed.
- If a token has no binding for a given theme, omit that theme's set entry entirely (Penpot tolerates missing tokens in a set).
- If the primitive sets were rebuilt with different color names, primitive token names may have changed — re-resolve from the current set state.
- `active: false` is the safe default — only activate sets when the user explicitly confirms they want semantic tokens applied to shapes.
- Use `penpot_api_info` to look up `TokenCatalog`, `TokenSet`, `TokenTheme` API details at execution time.
