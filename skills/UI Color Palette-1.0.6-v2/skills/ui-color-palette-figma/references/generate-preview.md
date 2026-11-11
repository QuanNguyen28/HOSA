---
name: ui-color-palette-figma-generate-preview
description: Draw a palette swatch board directly on the Figma canvas as a visual preview. Uses Auto Layout frames. Not a style/variable/token export — canvas rendering only.
---

# Generate Palette Preview — Figma

Draw a palette swatch board directly on the canvas using the Figma MCP API. This is a **canvas rendering**, not a style or variable export.

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
║ Couleurs src   ║  80   ║  70   ║  60   ║  50   ║  40   ║  30   ║  20   ║ 10 ║
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

Each shade cell — `_top` anchors top, `_bottom` anchors bottom via `space-between`:

```
╔══════════════════════╗
║ [80]      [#3B5BDB]  ║  ← _scale chip (left) + _hex chip (right, in _base)
║           [L·C·H]    ║  ← _oklch chip (right, in _base)
║                      ║
║                      ║  ← large colored area (shade fill)
║                      ║
║ ●20.62  [AAA       ] ║  ← _wcag21-light row + score badge
║ ●Lc107  [Texte flu ] ║  ← _apca-light row + score badge
║ ●1.02   [A         ] ║  ← _wcag21-dark row + score badge
║ ●Lc0.0  [Éviter    ] ║  ← _apca-dark row + score badge
╚══════════════════════╝
```

> **Design system**: every chip/badge frame shares the same visual treatment — semi-transparent white bg, subtle border, pill shape. Text is always `#00212B`; the shade fill provides the color context behind the transparent overlay.

---

## Figma layer hierarchy

```
Frame "<palette>・<theme>・<preset>・<color-space>"   ← root, Auto Layout vertical, padding 32px, fill #FFFFFF
  Frame "_colors・do not edit any layer"               ← Auto Layout vertical, rowGap 16px, no fill, no padding

    Frame "_title"                                     ← Auto Layout horizontal, justifyContent space-between, height auto
      Frame "_palette-global"                          ← Auto Layout vertical, hSizing fill
        Frame "_name"                                  ← chip style (see below)
          Text "_text"                                 ← palette name, Martian Mono 20px 500, #00212B

      Frame "_palette-props"                           ← Auto Layout vertical, gap 8px, alignItems end
        Frame "_provider"                              ← chip, gap 8px, pl-8 pr-4 py-4
          Text "_text"                                 ← "Fournisseur : <name>", Martian Mono 12px 500, #00212B
          Frame "_avatar"                              ← 24×24px, image fill (circle)
        Frame "_theme"                                 ← chip, px-8 py-4
          Text "_text"                                 ← Martian Mono 12px 500, #00212B
        Frame "_preset"                                ← chip, px-8 py-4
        Frame "_color-space"                           ← chip, px-8 py-4
        Frame "_vision-simulation"                     ← chip, px-8 py-4
        Frame "_updated_at"                            ← chip, px-8 py-4

    Frame "_shades"                                    ← Auto Layout vertical, no gap, no padding

      Frame "_header"                                  ← Auto Layout horizontal, height 48px
        Frame "Couleurs sources" (220px)               ← header cell — name = i18n label from PaletteData
          Frame "_property"
            Frame "_label"
              Text "_text"                             ← Martian Mono 10px 500, #00212B
        Frame "80" (220px)                             ← one per shade step
          Frame "_property"
            Frame "_label"
              Text "_text"                             ← scale label e.g. "80"
        …

      Frame "<color name>" (e.g. "Primary")            ← Auto Layout horizontal, height 330px
        Frame "_source" (220px)                        ← no fill
          Frame "<color name>" (220×330px)             ← fill = source color, Auto Layout vertical, pad 8px, justifyContent end, gap 8
            Frame "_property"
              Frame "_label"
                Text "_text"                           ← color name, Martian Mono 10px 500, contrasted
        Frame "_shades"                                ← Auto Layout horizontal
          Frame "80" (220×330px)                       ← fill = shade hex, Auto Layout vertical, pad 8px, justifyContent end, gap 8
            Frame "_properties"                        ← fill both, Auto Layout vertical, justifyContent space-between
              Frame "_top"                             ← fill width, Auto Layout horizontal
                Frame "_scale"                         ← chip style, Auto Layout horizontal
                  Text "_text"                         ← scale number, Martian Mono 10px 500, #00212B
                Frame "_base"                          ← fill, Auto Layout vertical, gap 4, alignItems end
                  Frame "_hex"                         ← chip style
                    Text "_text"                       ← hex value, Martian Mono 8px 500, #00212B
                  Frame "_oklch"                       ← chip style
                    Text "_text"                       ← "L 0.45 • C 0.22 • H 265", Martian Mono 8px 500, #00212B
              Frame "_bottom"                          ← fill width, Auto Layout vertical
                Frame "_contrast-scores"               ← Auto Layout vertical, gap 4
                  Frame "_wcag21-light"                ← score row (see below)
                  Frame "_apca-light"
                  Frame "_wcag21-dark"
                  Frame "_apca-dark"
          Frame "70" …

      Frame "<next color name>" …

    Frame "_signature"                                 ← Auto Layout horizontal, justifyContent space-between
      Frame "_info"                                    ← Auto Layout vertical, gap 4
        Frame "_tagline"                               ← chip style
          Text "_text"                                 ← Martian Mono 10px 500, #00212B
        Frame "_url"                                   ← chip style
          Text "_text"                                 ← Lexend 8px 500, #00212B (hyperlink)
      Frame "_logotype"                                ← chip style, borderRadius 8px
        Frame "_vector"                                ← SVG image
```

### Score row structure

Each score row (`_wcag21-light`, `_apca-light`, etc.):

```
Frame "_wcag21-light"     ← chip style, pl-8 pr-2 py-2, gap 4, alignItems center
  Frame "_indicator"      ← 8×8px image asset (white dot for light rows, dark dot for dark rows)
  Text "_text"            ← ratio/Lc value, Martian Mono 8px 500, #00212B
  Frame "_wcag21-light-score"  ← score badge (chip style), fill = grade color
    Text "_text"          ← grade label, Martian Mono 8px 500, #00212B
```

---

## Chip / badge visual treatment

**Every** chip or badge frame in this design (including `_name`, `_scale`, `_hex`, `_oklch`, prop rows, score rows, score badges, `_tagline`, `_url`, `_logotype`) shares the same base style:

| Property | Value |
|---|---|
| Background | `rgba(255, 255, 255, 0.5)` |
| Border | `1px solid rgba(0, 33, 43, 0.05)` |
| Border radius | `16px` (all chips), `8px` (`_logotype` only) |
| Default padding | `4px 8px` (top/bottom 4, left/right 8) |
| Score row padding | `2px 2px 2px 8px` (pl 8, pr 2, py 2) |
| Provider row padding | `4px 4px 4px 8px` (pl 8, pr 4, py 4) |

Text is **always `#00212B`** regardless of the shade fill. The translucent white overlay provides visual separation from the shade color behind it.

---

## Dimensions reference

| Element | Value |
|---|---|
| Root padding | 32px all sides |
| Root fill | `#FFFFFF` |
| `_colors` wrapper gap | 16px |
| `_title` | justifyContent `space-between`, height auto |
| `_palette-props` gap | 8px |
| `_avatar` | 24×24px |
| Header row height | 48px |
| Header/source cell width | 220px |
| Color row height | 330px |
| Shade cell width | 220px |
| Shade cell padding | 8px all sides |
| Shade cell gap | 8px |
| Shade cell justifyContent | `end` |
| `_properties` sizing | fill both |
| `_properties` justifyContent | `space-between` |
| `_contrast-scores` gap | 4px |

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

All Martian Mono text uses `fontVariationSettings: "'wdth' 100"`.

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

| Frame | Example text (from API) | Source |
|---|---|---|
| `_provider` | `Fournisseur : Aurélien Grimaud` | `palette.providerLabel` + `palette.providerName` |
| `_theme` | `Mode : Light` | `palette.themeLabel` + `palette.theme` |
| `_preset` | `Préréglage : Custom, 10-100` | `palette.presetLabel` + `palette.preset` |
| `_color-space` | `Espace colorimétrique : OKLCH` | `palette.colorSpaceLabel` + `palette.colorSpace` |
| `_vision-simulation` | `Simulation de vision : None` | `palette.visionSimLabel` + `palette.visionSim` |
| `_updated_at` | `Mis à jour le : 02/11/2026` | `palette.updatedAtLabel` + `palette.updatedAt` |

Format: `"<label> : <value>"` regardless of locale.

---

## Score indicator images

`_indicator` is a **rendered image asset** (not a plain colored ellipse). Two assets are used:

| Rows | Image | Visual |
|---|---|---|
| `_wcag21-light`, `_apca-light` | `imgIndicator` | White dot (represents white background being tested) |
| `_wcag21-dark`, `_apca-dark` | `imgIndicator1` | Dark dot (represents dark background being tested) |

---

## Score badge fill colors

| Grade | Fill |
|---|---|
| `AAA`, `AA`, `Texte fluide`, `Texte de contenu`, `Titres` | `#87D0B1` (green) |
| `A`, `Éviter`, fail | `#D3B3C7` (pink-mauve) |

---

## Root frame naming convention

| Token | Value |
|---|---|
| Root frame name | `<palette name>・<theme>・<preset>・<color-space>` |
| Separator | `・` (U+30FB, katakana middle dot) |
| Example | `UICP Color Primitives・Light・Custom, 10-100・OKLCH` |

---

## Figma MCP API build sequence

1. **Root frame** — Auto Layout vertical, padding 32px, fill `#FFFFFF`, hug contents.
2. **`_colors・do not edit any layer`** — Auto Layout vertical, gap 16px, no fill, fill parent.
3. **`_title`** — Auto Layout horizontal, `space-between`, hug height. Append to `_colors`.
   - Left: `_palette-global` → `_name` chip → `_text` (20px).
   - Right: `_palette-props` (gap 8, align end) → one chip per prop row. `_provider` also contains `_avatar` (24×24 image).
4. **`_shades`** — Auto Layout vertical, no gap. Append to `_colors`.
   - `_header` (48px): source label chip + one chip per scale step, 220px wide each. Inside each: `_property > _label > _text`.
   - For each color family: row frame (Auto Layout horizontal, 330px):
     - `_source` (220px): `<colorName>` inner (220×330, fill = source color, pad 8, justify end) → `_property > _label > _text`.
     - `_shades` container: one shade cell (220×330, fill = shade hex, pad 8, justify end):
       - `_properties` (fill+fill, space-between): `_top` (fill, row) + `_bottom` (fill, col).
       - `_top`: `_scale` chip + `_base` (fill col, gap 4, align end) → `_hex` chip + `_oklch` chip.
       - `_bottom`: `_contrast-scores` (col gap 4) → 4 score rows (pl-8 pr-2 py-2, gap 4): indicator image + value text + score badge chip.
5. **`_signature`** — Auto Layout horizontal, `space-between`. Append to `_colors`.
   - Left: `_info` (col gap 4) → `_tagline` chip + `_url` chip (Lexend, underlined).
   - Right: `_logotype` chip (borderRadius 8) → `_vector` SVG image.
6. Place root frame at a clear, non-overlapping position on the current page.

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
| Source column header | i18n label from PaletteData (e.g. `Couleurs sources`) |
| Shade column header | `<scale>` (e.g. `80`) |
| Color row | `<color name>` (e.g. `Primary`) |
| Source outer frame | `_source` |
| Source inner frame | `<color name>` (same as row name) |
| Source/header label | `_property > _label > _text` |
| Shades container | `_shades` |
| Shade cell | `<scale>` (e.g. `80`) |
| Shade internals | `_properties > _top / _bottom` |
| Scale chip | `_scale` |
| Color values | `_base > _hex`, `_base > _oklch` |
| Score section | `_contrast-scores` |
| Score rows | `_wcag21-light`, `_apca-light`, `_wcag21-dark`, `_apca-dark` |
| Score indicator | `_indicator` |
| Score badge | `_wcag21-light-score`, `_apca-light-score`, `_wcag21-dark-score`, `_apca-dark-score` |
| Signature | `_signature > _info`, `_signature > _logotype` |
