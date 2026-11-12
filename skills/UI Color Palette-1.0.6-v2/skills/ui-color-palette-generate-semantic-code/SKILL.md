---
name: ui-color-palette-generate-semantic-code
description: Generate semantic code files alongside primitives by passing a color system configuration to generate_code. Use when the user wants design tokens or code that includes both primitive shades and semantic layer (role/prominence/state mappings). Requires a SystemConfiguration in context or gathered from the user.
argument-hint: <format> [color-space]
---

# Generate Semantic Code

Use the **ui-color-palette** MCP tool `generate_code` with a `system` parameter to produce **two output files**: a primitives file and a semantics file.

Building the color system taxonomy is handled by `ui-color-palette-build-color-system`. Primitive-only code export (no semantic layer) is handled by `ui-color-palette-generate-code`.

---

## Pre-flight — Check session state

Before asking any questions, check the conversation context.

### If `GeneratedSemanticCode[format]` is already in context

Display it directly without calling `generate_code` again. Only regenerate if the user changes a parameter or requests a fresh export.

### If `SystemConfiguration` is already in context

Skip Step 0 questions about the system. Use the existing `system` config.

### If `base` and `themes` are already in context

Reuse them. Do not call `get_palette` or `get_color_system` again.

### If neither `SystemConfiguration` nor `system` bindings are available

Ask the user to define the taxonomy first, or route to `ui-color-palette-build-color-system`.

---

## Step 0 — Gather parameters

### Required

**1. Palette inputs** — confirm `base` and `themes` are available. If not, recover from context or run `ui-color-palette-scale-palette` first.

**2. System configuration** — confirm `system` (schema + bindings) is available. If not, run `ui-color-palette-build-color-system` first or ask the user to provide the taxonomy.

**3. Format** — ask to choose. Default: `css`.

**4. Color space** — ask only for formats that use it (`css`, `scss`, `less`, `dtcg-tokens`). Default: `RGB`.

---

## Tool — `generate_code`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `base` | object | Yes | Base palette configuration |
| `themes` | array | Yes | Theme configurations |
| `format` | enum | No | Output format (default: `css`) |
| `colorSpace` | enum | No | Color space for output values (default: `RGB`) |
| `system` | object | Yes (for semantic) | `SystemConfiguration` — schema + bindings |

### `format` values and their two output files

| Value | Primitives file | Semantics file | `colorSpace` used? |
| ----- | --------------- | -------------- | ------------------ |
| `css` | `primitives.css` | `semantics.css` | Yes |
| `scss` | `primitives.scss` | `semantics.scss` | Yes |
| `less` | `primitives.less` | `semantics.less` | Yes |
| `tailwind-v3` | `primitives.js` | `semantics.js` | No |
| `tailwind-v4` | `primitives.css` | `semantics.css` | No |
| `dtcg-tokens` | `primitives.json` | `semantics.json` | Yes |
| `style-dictionary-v3` | `primitives.json` | `semantics.json` | No |
| `universal-json` | `primitives.json` | `semantics.json` | No |
| `native-tokens` | `tokens.json` (merged) | — | No |
| `swift-ui` | `Primitives.swift` | `SemanticTokens.swift` | No |
| `ui-kit` | `Primitives.swift` | `SemanticTokens.swift` | No |
| `compose` | `Primitives.kt` | `SemanticTokens.kt` | No |
| `resources` | `primitives.xml` | `semantics.xml` | No |
| `csv` | `primitives.csv` | `semantics.csv` | No |

`colorSpace` applies only to `css`, `scss`, `less`, and `dtcg-tokens`. Values: `RGB` · `LCH` · `OKLCH` · `LAB` · `OKLAB` · `HSL` · `HSLUV` · `HSV` · `CMYK` · `HEX` · `P3`

> **Note**: `native-tokens` (Tokens Studio) merges primitives and semantics into a single `tokens.json` with multiple sets when `system` is provided.

### What the output contains

**Primitives file** — same as without `system`: one variable/token per shade (e.g. `--blue-500`).

**Semantics file** — one variable/token per bound token path, referencing the primitive:
- Default theme block (`:root` / `$variables` / top-level object) uses the default theme's resolved ref.
- Per-theme override blocks are only emitted when a token's ref **differs** from the default — excluded tokens are omitted entirely.

Unbound tokens (no binding or ref not found in palette) appear as comments in the semantics file.

---

## Workflow

1. Confirm `base`, `themes`, and `system` are available.
2. Ask for `format` (and `colorSpace` if applicable) if not already specified.
3. Call `generate_code` with `base`, `themes`, `format`, `colorSpace` (if applicable), and `system`.
4. **Session state**: store result as `GeneratedSemanticCode[format]` slot.
5. **Do not read or analyze the returned files.** Present each file as-is in its own fenced code block, labelled with the filename. Do not parse, summarize, or reason over the content — the output can be very large.
6. Offer to write the files locally or commit via `gh-cli` / `gitlab-cli-skills`.

---

## Arguments

`$ARGUMENTS` can specify the target format or color space.

- `/ui-color-palette:generate-semantic-code css oklch`
- `/ui-color-palette:generate-semantic-code dtcg-tokens`
- `/ui-color-palette:generate-semantic-code tailwind-v4`

## Tips

- **Format recommendations**: prefer `tailwind-v4` for new web projects, `dtcg-tokens` for design token interoperability, `css` for maximum compatibility.
- **Excluded tokens**: tokens with `isExcluded: true` are present in `SystemData` but do not appear in the semantics file output.
- **Unbound tokens**: appear as commented-out hints in the semantics output so the user can see what needs a binding.
- **Primitives unchanged**: the primitives file is identical whether `system` is provided or not — the semantic layer is purely additive.

---

## Recommended subagents

- **`uicper`** — orchestrates the full source → palette → system → deploy workflow
- **`palette-codegen`** — normalized multi-format token and code export agent
- **`gh-cli`** — commit and open a PR on GitHub
- **`gitlab-cli-skills`** — commit and open an MR on GitLab
