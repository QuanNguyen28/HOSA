---
name: ui-color-palette-scale-palette
description: Build a full color palette from source colors. Uses get_palette to generate scales and themes, then previews the result visually. Use when the user wants to create a complete palette before auditing, exporting, or deploying it.
argument-hint: <color-space>
---

# Build Palette

Use the **ui-color-palette** MCP tool `get_palette` to build a complete palette, then preview it visually.

Code export is handled by `ui-color-palette-generate-code`. Design tool deployment is handled by `ui-color-palette-figma`, `ui-color-palette-penpot`, `ui-color-palette-framer`, and `ui-color-palette-sketch`.

---

## Pre-flight — Check session state

Before asking any questions, check the conversation context for existing slots.

### If `PaletteData` is already in context

Inform the user of the existing palette (name, color space, preset) and ask: reuse, rebuild, or start from scratch. Wait for reply — if reuse, skip to visual preview.

### If `PublishedPaletteConfig` is already in context

**Skip Step 0 entirely** and go straight to Step 1. Inform the user: building from the loaded palette now.

Map the `PublishedPaletteConfig` fields to the `get_palette` input:

| `PublishedPaletteConfig` field | maps to |
| ------------------------------ | ------- |
| `name` | `base.name` |
| `description` | `base.description` |
| `preset` | `base.preset` |
| `shift` | `base.shift` |
| `are_source_colors_locked` | `base.areSourceColorsLocked` |
| `colors` | `base.colors` |
| `color_space` | `base.colorSpace` |
| `algorithm_version` | `base.algorithmVersion` |
| `themes` | `themes` |

Call `get_palette` immediately with these mapped values.

---

### If `SourceColors` is already in context

Skip question 2 of Step 0. Show the existing colors (name + hex) and ask the user to confirm or change them.

---

## Step 0 — Gather parameters

**Ask these questions before calling `get_palette`.** Do not call the tool until all required answers are collected. Stop after each question if the user hasn’t answered it yet.

### Required

**1. Palette name** — ask for a name.

**2. Source colors** — ask for role + hex per color (e.g. `primary #3B82F6`). Multiple colors allowed.

**3. Color space** — ask to choose: `OKLCH` (recommended), `LCH`, `OKLAB`, `HSL`, `P3`, or other.

**4. Scale preset** — ask to choose from the supported presets below. Suggest the most common ones first (`MATERIAL`, `TAILWIND`, `ANT`, `RADIX`) and mention others are available on request.

**Supported presets** (full list — `id` must be one of these exact values):

| Family | id | stops | min | max | easing |
| ------ | -- | ----- | --- | --- | ------ |
| Custom | `CUSTOM_1_10` | `[1,2,3,4,5,6]` | 10 | 90 | `LINEAR` |
| Custom | `CUSTOM_10_100` | `[10,20,30,40,50,60]` | 10 | 90 | `LINEAR` |
| Custom | `CUSTOM_100_1000` | `[100,200,300,400,500,600]` | 10 | 90 | `LINEAR` |
| Google | `MATERIAL` | `[50,100,200,300,400,500,600,700,800,900]` | 24 | 96 | `LINEAR` |
| Google | `MATERIAL_3` | `[100,99,95,90,80,70,60,50,40,30,20,10,0]` | 0 | 100 | `NONE` |
| Framework | `TAILWIND` | `[50,100,200,300,400,500,600,700,800,900,950]` | 16 | 96 | `LINEAR` |
| Framework | `ANT` | `[1,2,3,4,5,6,7,8,9,10]` | 24 | 96 | `LINEAR` |
| Framework | `BOOTSTRAP` | `[100,200,300,400,500,600,700,800,900]` | 15 | 95 | `LINEAR` |
| Framework | `RADIX` | `[1,2,3,4,5,6,7,8,9,10,11,12]` | 5 | 95 | `LINEAR` |
| Framework | `UNTITLED_UI` | `[25,50,100,200,300,400,500,600,700,800,900,950]` | 5 | 100 | `LINEAR` |
| Framework | `OPEN_COLOR` | `[0,1,2,3,4,5,6,7,8,9]` | 15 | 100 | `LINEAR` |
| Atlassian | `ADS` | `[100,200,300,400,500,600,700,800,900,1000]` | 24 | 96 | `LINEAR` |
| Atlassian | `ADS_NEUTRAL` | `[0,100,200,300,400,500,600,700,800,900,1000,1100]` | 8 | 100 | `LINEAR` |
| Adobe | `SPECTRUM` | `[100,200,300,400,500,600,700,800,900,1000,1100,1200,1300]` | 16 | 96 | `LINEAR` |
| Adobe | `SPECTRUM_NEUTRAL` | `[50,75,100,200,300,400,500,600,700,800,900]` | 0 | 100 | `LINEAR` |
| More | `CARBON` | `[10,20,30,40,50,60,70,80,90,100]` | 24 | 96 | `LINEAR` |
| More | `BASE` | `[50,100,200,300,400,500,600,700]` | 24 | 96 | `LINEAR` |
| More | `POLARIS` | `[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]` | 16 | 100 | `EASEOUT_QUAD` |
| More | `FLUENT` | `[10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160]` | 10 | 90 | `LINEAR` |

Always use the exact canonical `stops`, `min`, `max`, and `easing` for the chosen `id`. Never mix values from different presets.

**5. Themes** — ask: Light only, Light + Dark, or Custom.

### Optional (use defaults if not specified)

| Parameter | Default |
| --------- | ------- |
| Algorithm version | `v3` |
| Chroma shift | `100` (no change) |
| Hue shift | `0` (no rotation) |
| Source colors locked | `false` |

Once all required answers are collected, build the `get_palette` input and proceed to Step 1.

---

## Step 1 — Build the palette

**Tool**: `get_palette`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `base` | object | Yes | `BaseConfiguration` — palette base settings |
| `themes` | array | Yes | Array of `ThemeConfiguration` objects (light/dark modes) |

### `base` (BaseConfiguration) fields

| Field | Type | Description |
| ----- | ---- | ----------- |
| `name` | string | Palette name |
| `description` | string | Palette description |
| `preset` | object | `PresetConfiguration` — see below |
| `shift` | object | `ShiftConfiguration` — see below |
| `areSourceColorsLocked` | boolean | Whether source colors are pinned (default: `false`) |
| `colors` | array | Array of `ColorConfiguration` objects |
| `colorSpace` | string | One of: `LCH`, `OKLCH`, `LAB`, `OKLAB`, `HSL`, `HSLUV`, `HSV`, `CMYK`, `RGB`, `HEX`, `P3` |
| `algorithmVersion` | string | `"v1"`, `"v2"`, or `"v3"` |

### `PresetConfiguration`

Controls the lightness scale distribution. **`id` must be one of the 19 supported values** — see the full list in Step 0 question 4. Always use the canonical `stops`, `min`, `max`, and `easing` for the chosen `id`.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Preset identifier — must match exactly one of the supported preset ids |
| `name` | string | Display name matching the preset |
| `stops` | `number[]` | Scale stop labels — must match the canonical stops for the chosen id |
| `min` | number | Minimum lightness (darkest stop), 0–100 — must match the canonical min |
| `max` | number | Maximum lightness (lightest stop), 0–100 — must match the canonical max |
| `easing` | string | Distribution curve — must match the canonical easing for the chosen id |

### `ShiftConfiguration`

| Field | Type | Default (no change) | Description |
| ----- | ---- | ------------------- | ----------- |
| `chroma` | number | **`100`** | Global chroma/saturation shift — **100 = no change**, <100 = desaturate, >100 = saturate. Do not use 0 as a neutral value; 0 removes all saturation. |
| `hue` | number | `0` | Global hue rotation in degrees — 0 = no shift |

> **`shift.chroma` default is `100`, not `0`.** A value of 0 fully desaturates all colors.

### `ColorConfiguration` (each entry in `base.colors`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Auto-generated by the server — **do not set** |
| `name` | string | Color name (e.g. `"primary"`, `"neutral"`) |
| `description` | string | Color description |
| `rgb` | `{ r, g, b }` | RGB object, each value **0–1** (e.g. `{ r: 0.23, g: 0.51, b: 0.96 }` for #3B82F6) |
| `hue` | object | `{ shift: number, isLocked: boolean }` — per-color hue shift (default: `{ shift: 0, isLocked: false }`) |
| `chroma` | object | `{ shift: number, isLocked: boolean }` — per-color chroma shift (default: `{ shift: 100, isLocked: false }`) |
| `alpha` | object | `{ isEnabled: boolean, backgroundColor: string }` — alpha blending (default: `{ isEnabled: false, backgroundColor: "#FFFFFF" }`) |

### `ThemeConfiguration` (each entry in `themes`)

| Field | Type | Description |
| ----- | ---- | ----------- |
| `id` | string | Theme identifier. **`"00000000000"` is reserved exclusively for the default base theme (name `"None"`).** For any named theme (Light, Dark, etc.): generate a random 11-character lowercase hex string (e.g. `"9e3d5b0f12a"`). |
| `name` | string | Theme name. **`"None"` is reserved exclusively for the default base theme (id `"00000000000"`).** For named themes: e.g. `"Light"`, `"Dark"`. |
| `description` | string | Theme description — use empty string if none |
| `scale` | `Record<string, number>` | Map of stop label → lightness value (0–100). Keys must match `preset.stops`. If omitted, a linear scale is auto-generated from the preset `min`/`max`. E.g. `{ "50": 96, "100": 88, ..., "900": 24 }` |
| `paletteBackground` | string | Background hex color (e.g. `"#FFFFFF"`) |
| `visionSimulationMode` | string | `"NONE"`, `"PROTANOMALY"`, `"PROTANOPIA"`, `"DEUTERANOMALY"`, `"DEUTERANOPIA"`, `"TRITANOMALY"`, `"TRITANOPIA"`, `"ACHROMATOMALY"`, `"ACHROMATOPSIA"` |
| `textColorsTheme` | object | `{ lightColor: string, darkColor: string }` — default: `{ lightColor: "#FFFFFF", darkColor: "#000000" }` |
| `isEnabled` | boolean | Whether the theme is active — use `true` |
| `type` | string | `"default theme"` is reserved for the base theme (`id: "00000000000"`, `name: "None"`). All named themes (Light, Dark, etc.) must use `"custom theme"`. |

**Single vs. multi-theme:**

| Scenario | `id` | `name` | `type` |
| -------- | ---- | ------ | ------ |
| Single theme (no dark mode) | `"00000000000"` | `"None"` | `"default theme"` |
| Multi-theme — base (always present) | `"00000000000"` | `"None"` | `"default theme"` |
| Multi-theme — each named theme | random 11-char hex | `"Light"`, `"Dark"`, etc. | `"custom theme"` |

**Rule**: the default base theme (`00000000000` / `None` / `"default theme"`) is **always included** in the themes array, whether or not named themes are present.

**Returns**: A `PaletteData` object containing `name`, `description`, `themes` (with full color scales), and `type`.

---

## Step 2 — Visual preview

After `get_palette` returns, always ask:

> Do you want to see a visual preview of the palette?
> - **Yes** — show a preview
> - **No** — skip to next step

### Priority order

Apply the following priority — stop at the first option that works:

#### 1. Native UI preview (preferred)

Render the palette directly in the conversation without any external call. Produce a markdown table with one column per shade and one row per color, using the `hex` values from the compact cells:

```
Light — Primary
| 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 |
|#f0f4ff|#e8eeff|...|
```

If the chat interface supports HTML artifacts or rich rendering (Claude.ai, Jupyter, VS Code), prefer a richer layout. This requires no external tool call and works everywhere.

**Only proceed to option 2 if** the user explicitly says the native rendering is insufficient, or if they already mentioned a design tool in context.

#### 2. Design tool canvas

If the user has a design tool connected (Figma, Penpot, Sketch, Framer), offer to draw the palette directly into the current document as a visual swatch board. This is a **canvas rendering**, not a token/style/variable export:

> I can draw the palette directly in your document as a swatch board.

Use the design tool's MCP API to create the shapes directly. Do not invoke `ui-color-palette-figma`, `ui-color-palette-penpot`, `ui-color-palette-framer`, or `ui-color-palette-sketch` — those skills are for token/style/variable export, not canvas rendering.

For the exact layer hierarchy, layout primitives, swatch dimensions, and text specs, read the matching reference file before generating:

| Tool | Reference |
|---|---|
| Figma | `ui-color-palette-figma/references/generate-preview.md` |
| Penpot | `ui-color-palette-penpot/references/generate-preview.md` |
| Sketch | `ui-color-palette-sketch/references/generate-preview.md` |
| Framer | `ui-color-palette-framer/references/generate-preview.md` |

The visual output is identical across all tools: same swatch dimensions (64×80 px), same label layout (shade name + hex, plus optional contrast scores), same color hierarchy (root → theme → color row → swatches). Only the layout primitive names differ per tool (Auto Layout / Flex Layout / Stack / Layout).

#### 3. MCP preview image (fallback)

Only if neither option above is usable, call `preview_palette` with the cells from `get_palette` (compact: true). It returns a markdown image link served by the API:

```md
![palette preview](https://...)
```

Embed it in the reply. This requires an external HTTP call and the image may not render in all UIs.

### Branch B — No preview requested

Skip entirely. Do not call `preview_palette`.

---

## Step 3 — Contrast scores (optional)

After the preview step (whether or not an image was shown), ask:

> Do you want contrast scores displayed for this palette?
> - **WCAG** — ratio against light text (`#FFFFFF`) and dark text (`#000000`), with AA/AAA grades
> - **APCA** — Lc value against light and dark text, with recommended usage
> - **No scores** — skip

Default: **No scores** — proceed without asking if the user has already stated a preference.

### If WCAG or APCA requested

The compact cells from `get_palette` already include `textContrast`. Use those values — **do not re-call `get_palette`**.

For each theme, render a table:

| Color | Shade | Hex | Light text | Dark text |
| ----- | ----- | --- | ---------- | --------- |
| Primary | 50 | #f0f4ff | WCAG 1.2:1 F | WCAG 19.4:1 AAA |
| Primary | 500 | #3b5bdb | WCAG 4.6:1 AA | WCAG 4.5:1 AA |

For APCA, replace ratio/score columns with Lc values and `recommendedUsage` (e.g. `BODY_TEXT`, `SPOT_TEXT`, `NON_TEXT`, `AVOID`).

Only show scores for the themes and colors the user cares about — do not dump all shades unless asked.

If direct write-back tooling is available for the target design tool, use it. Otherwise:

1. build the palette with `get_palette`
2. extract only `theme.name`, `color.name`, `shade.name`, `shade.hex`, and preferred text color
3. create a compact swatch matrix spec
4. hand that spec off to the relevant design workflow/tool

### Example `get_palette` input — single theme (no dark mode)

```json
{
  "base": {
    "name": "My Palette",
    "description": "",
    "preset": {
      "id": "MATERIAL",
      "name": "Material Design",
      "stops": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900],
      "min": 24,
      "max": 96,
      "easing": "LINEAR"
    },
    "shift": { "chroma": 100, "hue": 0 },
    "areSourceColorsLocked": false,
    "colors": [
      {
        "name": "primary",
        "description": "",
        "rgb": { "r": 0.23, "g": 0.51, "b": 0.96 },
        "hue": { "shift": 0, "isLocked": false },
        "chroma": { "chroma": 100, "isLocked": false },
        "alpha": { "isEnabled": false, "backgroundColor": "#FFFFFF" }
      }
    ],
    "colorSpace": "OKLCH",
    "algorithmVersion": "v3"
  },
  "themes": [
    {
      "id": "00000000000",
      "name": "None",
      "description": "",
      "paletteBackground": "#FFFFFF",
      "visionSimulationMode": "NONE",
      "textColorsTheme": { "lightColor": "#FFFFFF", "darkColor": "#000000" },
      "isEnabled": true,
      "type": "default theme"
    }
  ]
}
```

### Example `get_palette` input — Light + Dark themes

```json
{
  "base": { "...same as above..." },
  "themes": [
    {
      "id": "00000000000",
      "name": "None",
      "description": "",
      "paletteBackground": "#FFFFFF",
      "visionSimulationMode": "NONE",
      "textColorsTheme": { "lightColor": "#FFFFFF", "darkColor": "#000000" },
      "isEnabled": true,
      "type": "default theme"
    },
    {
      "id": "9e3d5b0f12a",
      "name": "Light",
      "description": "",
      "scale": { "50": 96, "100": 88, "200": 80, "300": 72, "400": 64, "500": 56, "600": 48, "700": 40, "800": 32, "900": 24 },
      "paletteBackground": "#FFFFFF",
      "visionSimulationMode": "NONE",
      "textColorsTheme": { "lightColor": "#FFFFFF", "darkColor": "#000000" },
      "isEnabled": true,
      "type": "custom theme"
    },
    {
      "id": "4a7f2c1e09b",
      "name": "Dark",
      "description": "",
      "scale": { "50": 24, "100": 32, "200": 40, "300": 48, "400": 56, "500": 64, "600": 72, "700": 80, "800": 88, "900": 96 },
      "paletteBackground": "#1A1A1A",
      "visionSimulationMode": "NONE",
      "textColorsTheme": { "lightColor": "#FFFFFF", "darkColor": "#000000" },
      "isEnabled": true,
      "type": "custom theme"
    }
  ]
}
```

---

## Workflow

1. Collect source colors from the user or from a previous **generate-source-colors** step.
2. Call `get_palette` with a `BaseConfiguration` and at least one `ThemeConfiguration`. The response is a **flat array** of shade rows (compact mode is on by default).
3. **NEVER read, print, or reason from the full array.** Immediately apply the stream-extract below and discard everything else:
   ```
   for each row in response:
     keep: row.theme, row.color, row.shade, row.hex
     STOP — do not read any other field on this row
   ```
   Store the raw response opaquely as the `PaletteData` slot (passed as-is to downstream tools that need it). Reason only from the extracted swatch rows.
   If a downstream tool explicitly needs raw color space values (rgb, lch, etc.), recall `get_palette` with `compact: false` for that specific purpose.
   **Overflow handling**: If the response exceeds the maximum allowed tokens and is saved to disk, apply the following strategy depending on what is needed next — **do not read the file in chunks**:

   | Next operation | Strategy |
   |---|---|
   | Code export | Use `base` + `themes` directly → `generate_code`. `PaletteData` is not required. |
   | Display / preview | `grep` the overflow file for `"hex"` to extract one hex value per shade. Never read the file sequentially. |
   | Audit | `grep` the overflow file for `"hex"` and `"textContrast"` to extract contrast data per shade. Then delegate to `palette-auditor` with the extracted rows only. |
   | Design tool push | Use `base` + `themes` directly → matching deploy skill. `PaletteData` is not required. |

   In all cases, store a `PaletteData: overflow` marker in context so downstream tools know `PaletteData` is not available as an opaque object.
4. If the user asks for a visual preview, design handoff, or document generation, extract only the fields needed for a swatch matrix:
  - `theme.name`
  - `color.name`
  - `shade.name`
  - `shade.hex`
  - preferred text color if it can be inferred from `textColorsTheme` or audit data
5. **Ask the user what to do next.** Building the palette is not the end. The user may want to:
  - **Preview the palette visually** first — render a swatch matrix grouped by theme and color
  - **Generate it in a design tool** — route to `ui-color-palette-figma`, `ui-color-palette-penpot`, `ui-color-palette-framer`, or `ui-color-palette-sketch`
  - **Audit the palette** first — use `ui-color-palette-audit-palette` to check contrast and accessibility
  - **Publish the palette** — use `ui-color-palette-manage-palettes` to save it to the platform
  - **Export as code** — hand off to `ui-color-palette-generate-code`

## Arguments

`$ARGUMENTS` can be a color space or a description of the palette context.

- `/ui-color-palette:scale-palette oklch`
- `/ui-color-palette:scale-palette tailwind stops for my design system`
- `/ui-color-palette:scale-palette material dark and light themes`

## Tips

- **PaletteData**: Never read, print, or summarize the full JSON — the response is huge. Immediately stream-extract to swatch rows (`theme.name`, `color.name`, `shade.name`, `shade.hex`) and pass the raw object opaquely to downstream skills.
- **Hex → rgb 0–1**: divide each 0–255 channel by 255. E.g. `#3B82F6` → `{ r: 0.23, g: 0.51, b: 0.96 }`.
- **Scale without user input**: distribute lightness between `min` (last stop) and `max` (first stop). First stop → `max`, last → `min`.
- **Design-first requests**: board, canvas, swatches, style tiles → route to design tool skill first.
- **Code**: `generate_code` takes `base`+`themes` directly; prefer `dtcg-tokens`, `tailwind-v4`; `OKLCH`/`P3` for wide-gamut.

---

## Recommended subagents

- **`palette-codegen`** — normalizes `PaletteData` and generates code/tokens; use after this skill when code export is needed
- **`palette-transitioner`** — converts `PaletteData` into `variableRows`, `tokenRows`, `styleRows`, or `swatchRows` before routing to a platform workflow
