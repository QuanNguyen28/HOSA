---
name: ui-color-palette-generate-code
description: Export palette configuration as code or design tokens via the generate_code MCP tool using base and themes. Supports CSS, SCSS, Less, Tailwind v3/v4, SwiftUI, UIKit, Compose, Android resources, DTCG, Style Dictionary, CSV, and more.
argument-hint: <format> [color-space] [base+themes]
---

# Export Palette as Code

Use the **ui-color-palette** MCP tool `generate_code` to export palette configuration into the requested format.

`generate_code` now expects `base` and `themes` directly. A prior `get_palette` call is not required.

**Reuse rule — Palette Inputs**: If `base` and `themes` are already present in the conversation context, reuse them directly. Never regenerate the palette just to call `generate_code`.

**Reuse rule — GeneratedCode**: If code has already been generated for the requested format in this session, display it directly without calling `generate_code` again. Only regenerate if the user explicitly asks for a fresh export or changes a parameter (format, color space).

---

## Tool — `generate_code`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `base` | object | Yes | Base palette configuration |
| `themes` | array | Yes | Theme configurations (light/dark or other modes) |
| `format` | enum | No | Output format (default: `css`) |
| `colorSpace` | enum | No | Color space for output values (default: `RGB`) |

### `format` values

| Value | Description | `colorSpace` used? |
| ----- | ----------- | ------------------ |
| `css` | CSS custom properties | Yes |
| `scss` | SCSS variables | Yes |
| `less` | Less variables | Yes |
| `tailwind-v3` | Tailwind CSS v3 config | No |
| `tailwind-v4` | Tailwind CSS v4 `@theme` block | No |
| `swift-ui` | SwiftUI `Color` extensions | No |
| `ui-kit` | UIKit `UIColor` extensions | No |
| `compose` | Jetpack Compose constants | No |
| `resources` | Android XML color resources | No |
| `csv` | CSV spreadsheet | No |
| `native-tokens` | Native JSON token format | No |
| `dtcg-tokens` | DTCG JSON | Yes |
| `style-dictionary-v3` | Style Dictionary v3 | No |
| `universal-json` | Universal JSON flat key/value | No |

`colorSpace` applies only to `css`, `scss`, `less`, and `dtcg-tokens`. Values: `RGB` · `LCH` · `OKLCH` · `LAB` · `OKLAB` · `HSL` · `HSLUV` · `HSV` · `CMYK` · `HEX` · `P3`

---

## Workflow

1. Ask which `format` (and `colorSpace` if applicable) if not already specified.
2. Confirm `base` and `themes` are available. If missing, ask for them or recover them from prior palette configuration context.
3. Call `generate_code` with `base`, `themes`, and chosen parameters.
4. **Do not read or analyze the returned code.** Present it directly in a fenced code block as returned by the tool. Do not parse, summarize, or reason over its content — the output can be very large.
5. Offer to write it to a file or open a PR via `gh-cli` / `gitlab-cli-skills`.

**Format hints**: prefer `tailwind-v4` over v3 for new projects — prefer `dtcg-tokens` for token interoperability.

Delegate this skill to **`palette-codegen`** for multi-format or normalized projection workflows.

- **`palette-codegen`** — validates `base` and `themes`, selects the right projection, and generates code in the requested format
