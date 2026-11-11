---
name: ui-color-palette-sketch-generate-preview
description: Draw a palette swatch board directly on the Sketch canvas as a visual preview. Uses Groups on an Artboard. Not a style/swatch export — canvas rendering only.
---

# Generate Palette Preview — Sketch

Draw a palette swatch board directly on the canvas using the Sketch MCP API. This is a **canvas rendering**, not a style or swatch export.

---

## Target visual structure

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║ [Palette Name]        Fournisseur : Name  [avatar]                            ║
║                       Mode : Light                                            ║
║                       Préréglage : Custom, 10-100                             ║
║                       Espace colorimétrique : OKLCH                           ║
║                       Simulation de vision : None                             ║
║                       Mis à jour le : 02/11/2026                              ║
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
║ [Tagline]                                                      [Logotype]     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

Each shade cell — `_top` at top, `_bottom` at bottom:

```
╔══════════════════════╗
║ [80]      [#3B5BDB]  ║  ← _scale chip (left) + _hex chip (right, in _base)
║           [L·C·H]    ║  ← _oklch chip (right, in _base)
║                      ║
║                      ║  ← colored area (Group fill = shade hex)
║                      ║
║ ●20.62  [AAA       ] ║  ← _wcag21-light + score badge
║ ●Lc107  [Fluent txt] ║  ← _apca-light + score badge
║ ●1.02   [A         ] ║  ← _wcag21-dark + score badge
║ ●Lc0.0  [Avoid     ] ║  ← _apca-dark + score badge
╚══════════════════════╝
```

> **Sketch specifics**: the shade cell is a **Group whose own fill** provides the colored background (no separate Rectangle layer). Chip frames are also Groups with fills. Score indicators are `ShapePath` circles, not Ovals.

---

## Sketch layer hierarchy

```
Artboard "<palette>・<theme>・<preset>・<color-space>"  ← root, fill #FFFFFF
  Group "_colors・do not edit any layer"                ← padding 32px

    Group "_title"                                     ← horizontal, height 172, space-between
      Group "_palette-global"                          ← vertical
        Group "_name"                                  ← chip style
          Text "_text"                                 ← palette name, Martian Mono 20px 500, #00212B

      Group "_palette-props"                           ← vertical, gap 8, align right
        Group "_provider"                              ← chip, horizontal, gap 8
          Text "_text"                                 ← "Fournisseur : <name>", Martian Mono 12px 500, #00212B
          ShapePath "_avatar"                          ← 24×24px circle, image fill
        Group "_theme"                                 ← chip
        Group "_preset"                                ← chip
        Group "_color-space"                           ← chip
        Group "_vision-simulation"                     ← chip
        Group "_updated_at"                            ← chip

    Group "_shades"                                    ← vertical, no gap

      Group "_header"                                  ← horizontal, height 48
        Group "Source colors" (220px)                  ← header cell — name = i18n label from PaletteData
          Group "_property"
            Group "_label"
              Text "_text"                             ← Martian Mono 10px 500, #00212B
        Group "80" (220px)                             ← one per shade step
          Group "_property"
            Group "_label"
              Text "_text"                             ← scale label e.g. "80"
        …

      Group "<color name>" (e.g. "Primary")            ← horizontal, height 330
        Group "_source" (220px)
          Group "<color name>" (220×330)               ← fill = source color, vertical, pad 8, justify end, gap 8
            Group "_property"
              Group "_label"
                Text "_text"                           ← color name, Martian Mono 10px 500, #00212B
        Group "_shades"                                ← horizontal
          Group "80" (220×330)                         ← fill = shade hex on the Group itself (no Rectangle child)
            Group "_properties"                        ← 204×314, vertical, space-between
              Group "_top"                             ← 204×36, horizontal
                Group "_scale"                         ← chip style
                  Text "_text"                         ← scale number, Martian Mono 10px 500, #00212B
                Group "_base"                          ← vertical, gap 4, align right
                  Group "_hex"                         ← chip style
                    Text "_text"                       ← hex value, Martian Mono 8px 500, #00212B
                  Group "_oklch"                       ← chip style
                    Text "_text"                       ← "L 0.45 • C 0.22 • H 265", Martian Mono 8px 500, #00212B
              Group "_bottom"                          ← 204×92, vertical
                Group "_contrast-scores"               ← vertical, gap 4
                  Group "_wcag21-light"                ← score row (see below)
                  Group "_apca-light"
                  Group "_wcag21-dark"
                  Group "_apca-dark"
          Group "70" …

      Group "<next color name>" …

    Group "_signature"                                 ← horizontal, space-between
      Group "_info"                                    ← vertical, gap 4
        Group "_tagline"                               ← chip style
          Text "_text"                                 ← Martian Mono 10px 500, #00212B
        Group "_url"                                   ← chip style
          Text "_text"                                 ← Lexend 8px 500, #00212B
      Group "_logotype"                                ← chip style
        (SVG vector or image)
```

### Score row structure

```
Group "_wcag21-light"          ← horizontal, gap 4, align center, chip style
  ShapePath "_indicator"       ← 8×8px circle, fill = bg test color
  Text "_text"                 ← ratio/Lc value, Martian Mono 8px 500, #00212B
  Group "_wcag21-light-score"  ← score badge (chip style), fill = grade color
    Text "_text"               ← grade label, Martian Mono 8px 500, #00212B
```

---

## Chip / badge visual treatment

Every chip or badge Group shares the same visual style:

| Property | Value |
|---|---|
| Background fill | `#FFFFFF` at 50% opacity (`#ffffff80`) |
| Border radius | via `cornerRadius` on the Group |
| Default padding | 4px top/bottom, 8px left/right |

Text is **always `#00212B`**. The translucent white overlay provides separation from the shade fill behind it.

> **Sketch note**: Groups in Sketch support fills directly. No separate Rectangle layer is needed for chip backgrounds.

---

## Dimensions reference

| Element | Value |
|---|---|
| Root Artboard fill | `#FFFFFF` |
| Root padding | 32px all sides |
| `_title` height | 172px |
| Header row height | 48px |
| Header/source cell width | 220px |
| Color row height | 330px |
| Shade cell width | 220px |
| Shade cell fill | shade hex on the Group (no child Rectangle) |
| `_properties` | 204×314px |
| `_top` height | 36px |
| `_bottom` height | 92px |
| Score indicator | ShapePath 8×8px circle |

---

## Typography reference

Content values are examples — all actual values come from `PaletteData` at runtime.

| Layer | Family | Size | Weight | Color |
|---|---|---|---|---|
| Palette name `_text` | Martian Mono | 20px | 500 | `#00212B` |
| Props rows `_text` | Martian Mono | 12px | 500 | `#00212B` |
| Header/source label `_text` | Martian Mono | 10px | 500 | `#00212B` |
| Scale badge `_text` | Martian Mono | 10px | 500 | `#00212B` |
| Hex `_text` | Martian Mono | 8px | 500 | `#00212B` |
| OKLCH `_text` | Martian Mono | 8px | 500 | `#00212B` |
| Score value `_text` | Martian Mono | 8px | 500 | `#00212B` |
| Score badge `_text` | Martian Mono | 8px | 500 | `#00212B` |
| Tagline `_text` | Martian Mono | 10px | 500 | `#00212B` |
| URL `_text` | Lexend | 8px | 500 | `#00212B` |

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

Labels are i18n strings from `PaletteData` — **do not hardcode them**:

| Frame | Example (English locale) | Source |
|---|---|---|
| `_provider` | `Fournisseur : Aurélien Grimaud` | `palette.providerLabel` + `palette.providerName` |
| `_theme` | `Mode : Light` | `palette.themeLabel` + `palette.theme` |
| `_preset` | `Préréglage : Custom, 10-100` | `palette.presetLabel` + `palette.preset` |
| `_color-space` | `Espace colorimétrique : OKLCH` | `palette.colorSpaceLabel` + `palette.colorSpace` |
| `_vision-simulation` | `Simulation de vision : None` | `palette.visionSimLabel` + `palette.visionSim` |
| `_updated_at` | `Mis à jour le : 02/11/2026` | `palette.updatedAtLabel` + `palette.updatedAt` |

Format: `"<label> : <value>"`. Labels vary by locale (e.g. `"Source colors"` in English, `"Couleurs sources"` in French).

---

## Score indicator fill colors

`_indicator` is a `ShapePath` (circle) — **not an Oval layer**:

| Row | Fill |
|---|---|
| `_wcag21-light`, `_apca-light` | `#FFFFFF` (white — light bg being tested) |
| `_wcag21-dark`, `_apca-dark` | `#000000` (black — dark bg being tested) |

---

## Score badge fill colors

| Grade | Fill |
|---|---|
| `AAA`, `AA`, `Fluent text`, `Body text` (pass) | `#87D0B1` |
| `A`, `Avoid`, fail | `#D3B3C7` |

---

## Root frame naming convention

| Token | Value |
|---|---|
| Root Artboard name | `<palette name>・<theme>・<preset>・<color-space>` |
| Separator | `・` (U+30FB, katakana middle dot) |
| Example | `UICP Color Primitives・Light・Custom, 10-100・OKLCH` |

---

## Sketch MCP API build sequence

1. **Root Artboard** — fill `#FFFFFF`, sized to content.
2. **`_colors・do not edit any layer`** — Group, 32px padding.
3. **`_title`** — horizontal Group, space-between.
   - Left: `_palette-global` → `_name` chip → `_text` (20px).
   - Right: `_palette-props` (gap 8, align right) → one chip Group per prop row. `_provider` also has `_avatar` ShapePath (24×24 circle, image fill).
4. **`_shades`** — vertical Group, no gap.
   - `_header` (48px): source label chip + one chip per scale step, 220px wide. Inside each: `_property > _label > _text`.
   - For each color family: horizontal Group (330px):
     - `_source` (220px): `<colorName>` Group (fill = source color, 220×330, pad 8, justify end) → `_property > _label > _text`.
     - `_shades` container: one shade Group per step (220×330, fill = shade hex **on the Group**):
       - `_properties` (204×314, vertical, space-between):
         - `_top` (204×36, horizontal): `_scale` chip + `_base` (vertical, gap 4, align right) → `_hex` chip + `_oklch` chip.
         - `_bottom` (204×92, vertical): `_contrast-scores` (vertical, gap 4) → 4 score rows (horizontal, chip style): ShapePath indicator (8×8) + value Text + score badge Group.
5. **`_signature`** — horizontal Group, space-between.
   - Left: `_info` (vertical, gap 4) → `_tagline` chip + `_url` chip (Lexend).
   - Right: `_logotype` Group.
6. Place Artboard on a page named `Palette Preview` (create the page if it doesn't exist).

---

## Naming convention

| Element | Name |
|---|---|
| Root Artboard | `<palette name>・<theme>・<preset>・<color-space>` |
| Inner wrapper | `_colors・do not edit any layer` |
| Title section | `_title` |
| Left title block | `_palette-global` |
| Right props block | `_palette-props` |
| Shades section | `_shades` |
| Header row | `_header` |
| Source column header | i18n label from PaletteData (e.g. `Source colors`) |
| Shade column header | `<scale>` (e.g. `80`) |
| Color row | `<color name>` (e.g. `Primary`) |
| Source outer group | `_source` |
| Source inner group | `<color name>` (same as row name) |
| Source/header label | `_property > _label > _text` |
| Shades container | `_shades` |
| Shade group | `<scale>` (e.g. `80`) |
| Shade internals | `_properties > _top / _bottom` |
| Scale chip | `_scale` |
| Color values | `_base > _hex`, `_base > _oklch` |
| Score section | `_contrast-scores` |
| Score rows | `_wcag21-light`, `_apca-light`, `_wcag21-dark`, `_apca-dark` |
| Score indicator | `_indicator` (ShapePath) |
| Score badge | `_wcag21-light-score`, `_apca-light-score`, `_wcag21-dark-score`, `_apca-dark-score` |
| Signature | `_signature > _info`, `_signature > _logotype` |
