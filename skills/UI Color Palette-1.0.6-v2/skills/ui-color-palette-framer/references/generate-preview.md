---
name: ui-color-palette-framer-generate-preview
description: Draw a palette swatch board directly on the Framer canvas as a visual preview. Uses Stack layouts. Not a style/token export — canvas rendering only.
---

# Generate Palette Preview — Framer

Draw a palette swatch board directly on the canvas using the Framer MCP API. This is a **canvas rendering**, not a style or token export.

---

## Target visual structure

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║ [Palette Name]        Provider: Name  [avatar]                                ║
║                       Mode: Light                                             ║
║                       Preset: Custom, 10-100                                  ║
║                       Color space: OKLCH                                      ║
║                       Vision simulation: None                                 ║
║                       Updated at: February 11, 2026                           ║
╠════════════════╦═══════╦═══════╦═══════╦═══════╦═══════╦═══════╦═══════╦════╣
║ Source colors  ║  80   ║  70   ║  60   ║  50   ║  40   ║  30   ║  20   ║ 10 ║
╠════════════════╬═══════╬═══════╬═══════╬═══════╬═══════╬═══════╬═══════╬════╣
║                ║ [80]  ║       ║       ║       ║       ║       ║       ║    ║
║ Primary        ║[#hex] ║       ║       ║       ║       ║       ║       ║    ║
║ (source color) ║[L·C·H]║       ║       ║       ║       ║       ║       ║    ║
║                ║●20.62 ║       ║       ║       ║       ║       ║       ║    ║
║                ║  AAA  ║       ║       ║       ║       ║       ║       ║    ║
╠════════════════╩═══════╩═══════╩═══════╩═══════╩═══════╩═══════╩═══════╩════╣
║ Neutral …                                                                     ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ [Tagline]  [URL]                                                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

Each shade cell — `_top` at top, `_bottom` at bottom:

```
╔══════════════════════╗
║ [80]      [#3B5BDB]  ║  ← _scale chip (left) + _hex chip (right, in _base)
║           [L·C·H]    ║  ← _oklch chip (right, in _base)
║                      ║
║                      ║  ← colored area (backgroundColor = shade hex)
║                      ║
║ ●●20.62  [AAA      ] ║  ← _wcag21-light + score badge
║ ●●Lc107  [Fluent t ] ║  ← _apca-light + score badge
║ ●●1.02   [A        ] ║  ← _wcag21-dark + score badge
║ ●●Lc0.0  [Avoid    ] ║  ← _apca-dark + score badge
╚══════════════════════╝
```

> **Framer specifics**: all text uses `font="Inter"`. Chip frames use `backgroundColor="#ffffff80"`. Score indicators are **Frames** (not ellipses) with `borderRadius="8px"`, **16×16px**. The `_logotype` may not be present in all palettes.

---

## Framer XML hierarchy

```xml
<Frame name="<palette>・<theme>・<preset>・<color-space>"
    position="absolute" width="fit-content" height="fit-content"
    backgroundColor="#FFFFFF" borderRadius="16px"
    layout="stack" padding="32px" stackDirection="vertical"
    stackDistribution="center" stackAlignment="center">

  <Frame name="_colors・do not edit any layer"
      width="fit-content" height="fit-content"
      layout="stack" gap="16px" stackDirection="vertical"
      stackDistribution="start" stackAlignment="start">

    <!-- TITLE -->
    <Frame name="_title"
        width="1fr" height="fit-content"
        layout="stack" stackDirection="horizontal"
        stackDistribution="space-between" stackAlignment="start">

      <Frame name="_palette-global"
          width="fit-content" height="fit-content"
          layout="stack" gap="8px" stackDirection="vertical"
          stackDistribution="start" stackAlignment="start">
        <Frame name="_name"
            backgroundColor="#ffffff80" borderRadius="16px"
            layout="stack" gap="4px" padding="4px 8px 4px 8px"
            stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
          <Text font="Inter">UICP Color Primitives</Text>
        </Frame>
      </Frame>

      <Frame name="_palette-props"
          width="fit-content" height="fit-content"
          layout="stack" gap="8px" stackDirection="vertical"
          stackDistribution="start" stackAlignment="end">
        <!-- Each prop row: same chip style, padding="4px 8px 4px 8px" -->
        <!-- _provider: padding="4px 4px 4px 8px" + Avatar frame 24×24 borderRadius="12px" -->
        <Frame name="_provider" backgroundColor="#ffffff80" borderRadius="16px"
            layout="stack" gap="4px" padding="4px 4px 4px 8px"
            stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
          <Text font="Inter">Provider: Aurélien Grimaud</Text>
          <Frame name="_avatar" width="24px" height="24px" borderRadius="12px"
              backgroundImage="<avatar-url>" />
        </Frame>
        <Frame name="_theme" backgroundColor="#ffffff80" borderRadius="16px"
            layout="stack" gap="4px" padding="4px 8px 4px 8px"
            stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
          <Text font="Inter">Mode: Light</Text>
        </Frame>
        <!-- _preset, _color-space, _vision-simulation, _updated_at: same structure -->
      </Frame>
    </Frame>

    <!-- SHADES -->
    <Frame name="_shades"
        width="fit-content" height="fit-content"
        layout="stack" stackDirection="vertical"
        stackDistribution="center" stackAlignment="center">

      <!-- HEADER -->
      <Frame name="_header"
          width="fit-content" height="fit-content"
          layout="stack" stackDirection="horizontal"
          stackDistribution="start" stackAlignment="start">
        <Frame name="Source colors" width="312px" height="48px"
            layout="stack" padding="8px" stackDirection="vertical"
            stackDistribution="start" stackAlignment="start">
          <Frame name="_property" width="1fr" height="1fr" layout="stack"
              stackDirection="vertical" stackDistribution="start" stackAlignment="start">
            <Frame name="_label" backgroundColor="#ffffff80" borderRadius="16px"
                layout="stack" gap="4px" padding="4px 8px 4px 8px"
                stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
              <Text font="Inter">Source colors</Text>
            </Frame>
          </Frame>
        </Frame>
        <!-- One per scale step: width="312px" height="48px", same inner structure -->
        <Frame name="80" width="312px" height="48px" ...>...</Frame>
      </Frame>

      <!-- COLOR ROW -->
      <Frame name="Primary"
          width="fit-content" height="fit-content"
          layout="stack" stackDirection="horizontal"
          stackDistribution="start" stackAlignment="start">

        <Frame name="_source" width="fit-content" height="fit-content"
            layout="stack" stackDirection="horizontal"
            stackDistribution="start" stackAlignment="start">
          <Frame name="Primary" width="312px" height="468px"
              backgroundColor="#fff700"
              layout="stack" gap="8px" padding="8px"
              stackDirection="vertical" stackDistribution="end" stackAlignment="start">
            <Frame name="_property" width="1fr" height="1fr" layout="stack" ...>
              <Frame name="_label" backgroundColor="#ffffff80" borderRadius="16px"
                  layout="stack" gap="4px" padding="4px 8px 4px 8px" ...>
                <Text font="Inter">Primary</Text>
              </Frame>
            </Frame>
          </Frame>
        </Frame>

        <Frame name="_shades" width="fit-content" height="fit-content"
            layout="stack" stackDirection="horizontal" ...>

          <!-- SHADE CELL -->
          <Frame name="80" width="312px" height="468px"
              backgroundColor="#0b0100"
              layout="stack" gap="8px" padding="8px"
              stackDirection="vertical" stackDistribution="end" stackAlignment="start">

            <Frame name="_properties" width="1fr" height="1fr"
                layout="stack" stackDirection="vertical"
                stackDistribution="space-between" stackAlignment="start">

              <Frame name="_top" width="1fr" height="fit-content"
                  layout="stack" stackDirection="horizontal"
                  stackDistribution="start" stackAlignment="start">
                <Frame name="_scale" backgroundColor="#ffffff80" borderRadius="16px"
                    layout="stack" gap="4px" padding="4px 8px 4px 8px"
                    stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
                  <Text font="Inter">80</Text>
                </Frame>
                <Frame name="_base" width="1fr" height="fit-content"
                    layout="stack" gap="4px" stackDirection="vertical"
                    stackDistribution="start" stackAlignment="end">
                  <Frame name="_hex" backgroundColor="#ffffff80" borderRadius="16px"
                      layout="stack" gap="4px" padding="4px 8px 4px 8px"
                      stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
                    <Text font="Inter">#0B0100</Text>
                  </Frame>
                  <Frame name="_oklch" backgroundColor="#ffffff80" borderRadius="16px"
                      layout="stack" gap="4px" padding="4px 8px 4px 8px"
                      stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
                    <Text font="Inter">L 0.1 • C 0.03 • H 38</Text>
                  </Frame>
                </Frame>
              </Frame>

              <Frame name="_bottom" width="1fr" height="fit-content"
                  layout="stack" stackDirection="vertical"
                  stackDistribution="start" stackAlignment="start">
                <Frame name="_contrast-scores" width="1fr" height="fit-content"
                    layout="stack" gap="4px" stackDirection="vertical"
                    stackDistribution="start" stackAlignment="start">

                  <!-- SCORE ROW -->
                  <Frame name="_wcag21-light" width="fit-content" height="fit-content"
                      backgroundColor="#ffffff80" borderRadius="16px"
                      layout="stack" gap="4px" padding="2px 2px 2px 8px"
                      stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
                    <Frame name="_indicator" width="16px" height="16px"
                        backgroundColor="#ffffff" borderRadius="8px" />
                    <Text font="Inter">20.62</Text>
                    <Frame name="_wcag21-light-score" backgroundColor="#87d0b1" borderRadius="16px"
                        layout="stack" gap="4px" padding="4px 8px 4px 8px"
                        stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
                      <Text font="Inter">AAA</Text>
                    </Frame>
                  </Frame>
                  <!-- _apca-light, _wcag21-dark, _apca-dark: same structure -->
                  <!-- Dark indicator: backgroundColor="#000000" -->
                  <!-- Fail badge: backgroundColor="#d3b3c7" -->

                </Frame>
              </Frame>

            </Frame>
          </Frame>
        </Frame>
      </Frame>
    </Frame>

    <!-- SIGNATURE -->
    <Frame name="_signature" width="1fr" height="fit-content"
        layout="stack" stackDirection="horizontal"
        stackDistribution="start" stackAlignment="start">
      <Frame name="_info" width="fit-content" height="fit-content"
          layout="stack" gap="4px" stackDirection="vertical"
          stackDistribution="start" stackAlignment="start">
        <Frame name="_tagline" backgroundColor="#ffffff80" borderRadius="16px"
            layout="stack" gap="4px" padding="4px 8px 4px 8px"
            stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
          <Text font="Inter">WCAG Color Palette Manager for Apps &amp; Websites</Text>
        </Frame>
        <Frame name="_url" backgroundColor="#ffffff80" borderRadius="16px"
            layout="stack" gap="4px" padding="4px 8px 4px 8px"
            stackDirection="horizontal" stackDistribution="center" stackAlignment="center">
          <Text font="Inter">www.ui-color-palette.com</Text>
        </Frame>
      </Frame>
      <!-- _logotype (optional): chip frame containing vector/image -->
    </Frame>

  </Frame>
</Frame>
```

---

## Dimensions reference

| Element | Value |
|---|---|
| Root fill | `#FFFFFF` |
| Root `borderRadius` | `16px` |
| Root `padding` | `32px` |
| `_colors` wrapper `gap` | `16px` |
| `_title` | `stackDistribution="space-between"`, `width="1fr"` |
| `_palette-global` gap | `8px` |
| `_palette-props` gap | `8px`, `stackAlignment="end"` |
| Header/source cell width | `312px` |
| Header cell height | `48px` |
| Color row height | `468px` |
| Shade cell width | `312px` |
| Shade cell `padding` | `8px` |
| Shade cell `gap` | `8px` |
| Shade cell `stackDistribution` | `end` |
| `_properties` | `width="1fr"`, `height="1fr"`, `space-between` |
| `_top` | `width="1fr"`, horizontal row |
| `_base` | `width="1fr"`, vertical, `stackAlignment="end"` (right-aligned) |
| `_bottom` / `_contrast-scores` gap | `4px` |
| Score indicator size | **16×16px** (Frame, not ellipse) |
| Score indicator `borderRadius` | `8px` |

---

## Chip / badge visual treatment

All chip frames share the same base style:

| Property | Value |
|---|---|
| `backgroundColor` | `#ffffff80` (white 50% opacity) |
| `borderRadius` | `16px` |
| Default `padding` | `4px 8px 4px 8px` |
| Score row `padding` | `2px 2px 2px 8px` (asymmetric) |
| Provider row `padding` | `4px 4px 4px 8px` (pr=4 to accommodate avatar) |
| `gap` | `4px` |
| `stackDirection` | `horizontal` |
| `stackDistribution` | `center` |
| `stackAlignment` | `center` |

---

## Typography reference

**All text in Framer uses `font="Inter"`** — there is no Martian Mono or Lexend in the canvas rendering.

Font size and weight are not set explicitly on text nodes (Framer defaults apply). Content values come from `PaletteData` at runtime.

| Layer | Content source |
|---|---|
| Palette name | `PaletteData.name` |
| Props rows | API label + value (see formats below) |
| Header/source label | scale step or i18n label |
| Scale chip | scale step (e.g. `80`) |
| Hex chip | shade hex (e.g. `#0B0100`) |
| OKLCH chip | `L 0.45 • C 0.22 • H 265` |
| Score value | WCAG ratio / APCA Lc value |
| Score badge | grade label from API |
| Tagline | `PaletteData.tagline` |
| URL | `PaletteData.url` |

---

## OKLCH value format

```
L 0.45 • C 0.22 • H 265
```

- `L` = lightness as decimal 0–1
- `C` = chroma
- `H` = hue angle (integer)
- Separator: ` • ` (space + bullet + space)

---

## Props row text formats

Labels are i18n from `PaletteData`. Framer uses English labels with `"label: value"` format (colon, no leading space):

| Frame | Example text | Source |
|---|---|---|
| `_provider` | `Provider: Aurélien Grimaud` | `palette.providerLabel` + `palette.providerName` |
| `_theme` | `Mode: Light` | `palette.themeLabel` + `palette.theme` |
| `_preset` | `Preset: Custom, 10-100` | `palette.presetLabel` + `palette.preset` |
| `_color-space` | `Color space: OKLCH` | `palette.colorSpaceLabel` + `palette.colorSpace` |
| `_vision-simulation` | `Vision simulation: None` | `palette.visionSimLabel` + `palette.visionSim` |
| `_updated_at` | `Updated at: February 11, 2026` | `palette.updatedAtLabel` + `palette.updatedAt` |

> Note: other platforms (Figma, Penpot, Sketch) use `"label : value"` (space-colon-space). Framer uses `"label: value"` (no leading space). Labels and format come from `PaletteData` regardless.

---

## Score indicator colors

`_indicator` is a **Frame** (not an ellipse), `16×16px`, `borderRadius="8px"`:

| Row | `backgroundColor` |
|---|---|
| `_wcag21-light`, `_apca-light` | `#ffffff` |
| `_wcag21-dark`, `_apca-dark` | `#000000` |

---

## Score badge fill colors

| Grade | `backgroundColor` |
|---|---|
| `AAA`, `AA`, `Fluent text`, `Body text` (pass) | `#87d0b1` |
| `A`, `Avoid`, fail | `#d3b3c7` |

---

## Root frame naming convention

| Token | Value |
|---|---|
| Root frame name | `<palette name>・<theme>・<preset>・<color-space>` |
| Separator | `・` (U+30FB, katakana middle dot) |
| Example | `UICP Color Primitives・Light・Custom, 10-100・OKLCH` |

---

## Framer MCP API build sequence

1. **Root frame** — `position="absolute"`, `width/height="fit-content"`, `backgroundColor="#FFFFFF"`, `borderRadius="16px"`, `layout="stack"`, `padding="32px"`, `stackDirection="vertical"`.
2. **`_colors・do not edit any layer`** — `layout="stack"`, `gap="16px"`, `stackDirection="vertical"`.
3. **`_title`** — horizontal, `stackDistribution="space-between"`, `width="1fr"`. Append to `_colors`.
   - Left: `_palette-global` (gap 8, vertical) → `_name` chip → `Text` (Inter).
   - Right: `_palette-props` (gap 8, vertical, alignEnd) → one chip per prop row. `_provider` has `Avatar` frame 24×24 `borderRadius="12px"`.
4. **`_shades`** — vertical stack. Append to `_colors`.
   - `_header`: horizontal, contains `"Source colors"` + one chip per scale step, each 312×48px, padding 8px, `_property > _label > Text`.
   - For each color family: horizontal row (`width/height="fit-content"`):
     - `_source`: `<colorName>` inner frame (312×468px, fill = source color, vertical, pad 8, end) → `_property > _label > Text`.
     - `_shades` container: one shade cell per step (312×468px, fill = shade hex, vertical, pad 8, end, gap 8):
       - `_properties` (1fr×1fr, vertical, space-between):
         - `_top` (1fr, horizontal): `_scale` chip + `_base` (1fr, vertical, gap 4, alignEnd) → `_hex` chip + `_oklch` chip.
         - `_bottom` (1fr, vertical): `_contrast-scores` (1fr, vertical, gap 4) → 4 score rows (chip style, `padding="2px 2px 2px 8px"`, gap 4): `_indicator` Frame (16×16, borderRadius 8) + Text + score badge chip.
5. **`_signature`** — horizontal, `width="1fr"`, `stackDistribution="start"`. Append to `_colors`.
   - `_info` (vertical, gap 4): `_tagline` chip + `_url` chip (both Inter).
   - `_logotype` (optional): chip frame with vector/image.
6. Place root frame at a clear position on the canvas.

---

## Naming convention

| Element | Name |
|---|---|
| Root frame | `<palette name>・<theme>・<preset>・<color-space>` |
| Inner wrapper | `_colors・do not edit any layer` |
| Title section | `_title` |
| Left title block | `_palette-global` |
| Right props block | `_palette-props` |
| Shades section | `_shades` |
| Header row | `_header` |
| Source column header | i18n label from PaletteData (e.g. `Source colors`) |
| Shade column header | `<scale>` (e.g. `80`) |
| Color row | `<color name>` (e.g. `Primary`) |
| Source outer frame | `_source` |
| Source inner frame | `<color name>` (same as row name) |
| Source/header label | `_property > _label > Text` |
| Shades container | `_shades` |
| Shade cell | `<scale>` (e.g. `80`) |
| Shade internals | `_properties > _top / _bottom` |
| Scale chip | `_scale` |
| Color values | `_base > _hex`, `_base > _oklch` |
| Score section | `_contrast-scores` |
| Score rows | `_wcag21-light`, `_apca-light`, `_wcag21-dark`, `_apca-dark` |
| Score indicator | `_indicator` (Frame 16×16) |
| Score badge | `_wcag21-light-score`, `_apca-light-score`, `_wcag21-dark-score`, `_apca-dark-score` |
| Signature | `_signature > _info`, `_signature > _logotype` |
