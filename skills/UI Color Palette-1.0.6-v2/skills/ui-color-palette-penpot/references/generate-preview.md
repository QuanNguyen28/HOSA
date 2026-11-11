---
name: ui-color-palette-penpot-generate-preview
description: Draw a palette swatch board directly on the Penpot canvas as a visual preview. Uses Flex Layout frames. Not a style/token export — canvas rendering only.
---

# Generate Palette Preview — Penpot

Draw a palette swatch board directly on the canvas using the Penpot MCP API. This is a **canvas rendering**, not a style or token export.

---

## Target visual structure

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║ Palette Name                              Fournisseur : Name  [avatar]        ║
║                                           Mode : Light                        ║
║                                           Préréglage : Custom, 10-100         ║
║                                           Espace colorimétrique : OKLCH       ║
║                                           Simulation de vision : None         ║
║                                           Mis à jour le : Wed Feb 11 2026     ║
╠════════════════╦═══════╦═══════╦═══════╦═══════╦═══════╦═══════╦═══════╦════╣
║ Couleurs src   ║  80   ║  70   ║  60   ║  50   ║  40   ║  30   ║  20   ║ 10 ║
╠════════════════╬═══════╬═══════╬═══════╬═══════╬═══════╬═══════╬═══════╬════╣
║                ║ [80]  ║       ║       ║       ║       ║       ║       ║    ║
║ Primary        ║ #hex  ║       ║       ║       ║       ║       ║       ║    ║
║ (source color) ║ L·C·H ║       ║       ║       ║       ║       ║       ║    ║
║                ║●20.62 ║       ║       ║       ║       ║       ║       ║    ║
║                ║  AAA  ║       ║       ║       ║       ║       ║       ║    ║
╠════════════════╬═══════╩═══════╩═══════╩═══════╩═══════╩═══════╩═══════╩════╣
║ Neutral        ║  …                                                          ║
╠════════════════╩═════════════════════════════════════════════════════════════╣
║ Tagline · www.ui-color-palette.com                             [Logotype]    ║
╚═════════════════════════════════════════════════════════════════════════════╝
```

Each shade cell:

```
╔══════════════════════╗
║ [80]      #3B5BDB    ║  ← scale badge (left) + hex (right, in _base)
║           L·C·H val  ║  ← OKLCH value (right, in _base)
║                      ║
║                      ║  ← large colored area (shade fill)
║                      ║
║ ● 20.62  [AAA]       ║  ← WCAG 2.1 vs white  (dot · ratio · grade badge)
║ ● Lc 107 [Texte flu] ║  ← APCA vs white      (dot · Lc value · usage badge)
║ ● 1.02   [A]         ║  ← WCAG 2.1 vs black
║ ● Lc 0.0 [Éviter]   ║  ← APCA vs black
╚══════════════════════╝
```

The `_top` content (scale badge + hex/OKLCH) anchors to the **top**, the contrast score rows anchor to the **bottom** via `justifyContent: space-between` on `_properties`.

---

## Penpot layer hierarchy

```
Frame "<palette>・<theme>・<preset>・<color-space>"   ← root, Flex column, fill #FFFFFF, padding 32px
  Frame "_colors・do not edit any layer"               ← Flex column, rowGap 16px, no fill, no padding

    Frame "_title"                                     ← Flex row, justifyContent: space-between, height auto
      Frame "_palette-global"                          ← Flex column, rowGap 8px, hSizing fill
        Frame "_name"
          Frame "_text"                                ← palette name, Martian Mono 20px 500, #00212B

      Frame "_palette-props"                           ← Flex column, rowGap 8px, hSizing auto
        Frame "_provider"                              ← Flex row, colGap 8px
          Frame "_text"                                ← "Fournisseur : <name>", Martian Mono 12px 500, #00212B
          Ellipse "_avatar"                            ← 24×24px, image fill
        Frame "_theme"                                 ← "Mode : <Light|Dark>", same text style
        Frame "_preset"                                ← "Préréglage : <preset>", same
        Frame "_color-space"                           ← "Espace colorimétrique : <OKLCH>", same
        Frame "_vision-simulation"                     ← "Simulation de vision : <value>", same
        Frame "_updated_at"                            ← "Mis à jour le : <date>", same

    Frame "_shades"                                    ← Flex column, no gap, no padding

      Frame "_header"                                  ← Flex row, height 48px
        Frame "Couleurs sources" (200px)               ← header label cell — name = i18n label from PaletteData
          Frame "_property"
            Frame "_label"
              Text "_text"                             ← scale label, Martian Mono 10px 500, #00212B
        Frame "80"  (200px)                            ← one per shade step
          Frame "_property"
            Frame "_label"
              Text "_text"                             ← "80", Martian Mono 10px 500, #00212B
        Frame "70"  (200px)
        …

      Frame "<color name>"                             ← Flex row, height 300px (e.g. "Primary")
        Frame "_source" (200px)                        ← hSizing auto, no fill
          Frame "<color name>" (200×300px)             ← fill = source color, Flex col, pad 8px, justifyContent end, rowGap 8
            Frame "_property"
              Frame "_label"
                Text "_text"                           ← color name, Martian Mono 10px 500, contrasted

        Frame "_shades"                                ← Flex row, hSizing auto
          Frame "80" (200×300px)                       ← shade cell, fill = shade color, Flex col, pad 8px, justifyContent end, rowGap 8
            Frame "_properties"                        ← fill both dimensions, Flex col, justifyContent space-between, alignItems stretch
              Frame "_top"                             ← fill width, auto height, Flex row, justifyContent start
                Frame "_scale"                         ← auto, Flex row, colGap 4, pad 4/8, fill #FFFFFF 50%, alignItems center
                  Text "_text"                         ← scale number e.g. "80", Martian Mono 10px 500, contrasted
                Frame "_base"                          ← fill, auto, Flex col, rowGap 4, alignItems end
                  Frame "_hex"
                    Text "_text"                       ← "#3B5BDB", Martian Mono 8px 500, contrasted
                  Frame "_oklch"
                    Text "_text"                       ← "L 0.1 • C 0.03 • H 38", Martian Mono 8px 500, contrasted
              Frame "_bottom"                          ← fill width, auto height, Flex col
                Frame "_contrast-scores"               ← Flex col, rowGap 4
                  Frame "_wcag21-light"                ← Flex row, colGap 4, alignItems center
                    Ellipse "_indicator"               ← 8×8px, fill #FFFFFF (white bg test)
                    Text "_text"                       ← "20.62", Martian Mono 8px 500, contrasted
                    Frame "_wcag21-light-score"        ← auto, pad 4/8, borderRadius 16, fill = grade color
                      Text "_text"                     ← "AAA", Martian Mono 8px 500, contrasted
                  Frame "_apca-light"                  ← same structure
                    Ellipse "_indicator"               ← fill #FFFFFF
                    Text "_text"                       ← "Lc 107", Martian Mono 8px 500, contrasted
                    Frame "_apca-light-score"
                      Text "_text"                     ← "Texte fluide", Martian Mono 8px 500, contrasted
                  Frame "_wcag21-dark"
                    Ellipse "_indicator"               ← fill #000000 (dark bg test)
                    Text "_text"                       ← "1.02"
                    Frame "_wcag21-dark-score"
                      Text "_text"                     ← "A"
                  Frame "_apca-dark"
                    Ellipse "_indicator"               ← fill #000000
                    Text "_text"                       ← "Lc 0.0"
                    Frame "_apca-dark-score"
                      Text "_text"                     ← "Éviter"
          Frame "70" …

      Frame "<next color name>" …

    Frame "_signature"                                 ← Flex row, justifyContent space-between, hSizing fill
      Frame "_info"                                    ← Flex col, rowGap 4
        Frame "_tagline"
          Text "_text"                                 ← tagline, Martian Mono 10px 500, #00212B
        Frame "_url"
          Text "_text"                                 ← "www.ui-color-palette.com", Lexend 8px 500, #00212B
      Frame "_logotype"                                ← SVG vector group (_vector)
```

---

## Dimensions reference

| Element | Property | Value |
|---|---|---|
| Root board | padding all sides | 32 px |
| Root board | fill | `#FFFFFF` |
| `_colors` wrapper | rowGap | 16 px |
| `_title` | height | auto (hug) |
| `_title` | justifyContent | `space-between` |
| `_palette-props` | rowGap | 8 px |
| `_avatar` ellipse | size | 24×24 px |
| Header row | height | 48 px |
| Header cell | width | 200 px |
| Header cell | padding | 8 px all sides |
| Source column | width | 200 px |
| Color row | height | 300 px |
| Shade cell | width | 200 px |
| Shade cell | padding | 8 px all sides |
| Shade cell | rowGap | 8 px |
| Shade cell | justifyContent | `end` |
| `_properties` | hSizing | `fill` |
| `_properties` | vSizing | `fill` |
| `_properties` | justifyContent | `space-between` |
| `_properties` | alignItems | `stretch` |
| `_scale` badge | padding | 4 top/bottom, 8 left/right |
| `_scale` badge | fill | `#FFFFFF` at 50% opacity |
| Score badge | padding | 4 top/bottom, 8 left/right |
| Score badge | borderRadius | 16 px |
| Score indicator dot | size | 8×8 px |

---

## Typography reference

Content values below are examples from one palette — all actual values come from `PaletteData` at runtime.

| Layer | Content source | Family | Size | Weight | Fixed color |
|---|---|---|---|---|---|
| Palette name `_text` | `PaletteData.name` | Martian Mono | 20 px | 500 | `#00212B` |
| Props rows `_text` | API label + value | Martian Mono | 12 px | 500 | `#00212B` |
| Header cell `_text` | scale step (e.g. `80`) | Martian Mono | 10 px | 500 | `#00212B` |
| Source name `_text` | color family name | Martian Mono | 10 px | 500 | contrasted |
| Scale badge `_text` | scale step (e.g. `80`) | Martian Mono | 10 px | 500 | contrasted |
| Hex `_text` | shade hex (e.g. `#3B5BDB`) | Martian Mono | 8 px | 500 | contrasted |
| OKLCH `_text` | computed from shade | Martian Mono | 8 px | 500 | contrasted |
| Score value `_text` | WCAG ratio / APCA Lc value | Martian Mono | 8 px | 500 | contrasted |
| Score badge `_text` | grade label from API | Martian Mono | 8 px | 500 | contrasted |
| Tagline `_text` | `PaletteData.tagline` | Martian Mono | 10 px | 500 | `#00212B` |
| URL `_text` | `PaletteData.url` | Lexend | 8 px | 500 | `#00212B` |

**Contrasted color**: `#FFFFFF` if background relative luminance < 0.179 (i.e. dark shade), otherwise `#00212B`.

---

## OKLCH value format

Values displayed in the `_oklch` frame follow this exact format:

```
L 0.45 • C 0.22 • H 265
```

- `L` = lightness as decimal 0–1 (not percentage)
- `C` = chroma
- `H` = hue angle (integer)
- Separator: ` • ` (space + bullet + space)

---

## Props row text formats

All `_palette-props` rows use the label+value format `"<label> : <value>"` from `PaletteData`. Labels are i18n strings returned by the API — **do not hardcode them**. The example below shows French labels from one palette:

| Frame | Example text (from API) | `PaletteData` field |
|---|---|---|
| `_provider` | `Fournisseur : Aurélien Grimaud` | `palette.providerLabel` + `palette.providerName` |
| `_theme` | `Mode : Light` | `palette.themeLabel` + `palette.theme` |
| `_preset` | `Préréglage : Custom, 10-100` | `palette.presetLabel` + `palette.preset` |
| `_color-space` | `Espace colorimétrique : OKLCH` | `palette.colorSpaceLabel` + `palette.colorSpace` |
| `_vision-simulation` | `Simulation de vision : None` | `palette.visionSimLabel` + `palette.visionSim` |
| `_updated_at` | `Mis à jour le : Wed Feb 11 2026` | `palette.updatedAtLabel` + `palette.updatedAt` |

Use whatever label strings the API provides. The format is always `"<label> : <value>"` regardless of locale.

---

## Score indicator fill colors

| Row | Background being tested | `_indicator` fill |
|---|---|---|
| `_wcag21-light` | White (`#FFFFFF`) | `#FFFFFF` |
| `_apca-light` | White (`#FFFFFF`) | `#FFFFFF` |
| `_wcag21-dark` | Black (`#000000`) | `#000000` |
| `_apca-dark` | Black (`#000000`) | `#000000` |

The indicator represents **which background** is being tested, not the pass/fail result.

---

## Score badge fill colors (grade → fill)

| WCAG 2.1 grade | Fill |
|---|---|
| `AAA` | `#87D0B1` (green) |
| `AA` | `#87D0B1` (green) |
| `A` | `#F5CF87` (amber) |
| `—` (fail) | `#F5A0A0` (red-pink) |

| APCA usage label | Fill |
|---|---|
| `Texte fluide` / Body | `#87D0B1` |
| `Titres` / Large | `#87D0B1` |
| `Texte d'accentuation` | `#F5CF87` |
| `Texte de contenu` | `#87D0B1` |
| `Non-textuel` | `#F5CF87` |
| `Éviter` / Avoid | `#F5A0A0` |

---

## Root frame naming convention

| Token | Value |
|---|---|
| Root frame name | `<palette name>・<theme>・<preset>・<color-space>` |
| Separator | `・` (U+30FB, katakana middle dot) |
| Example | `UICP Color Primitives・Light・Custom, 10-100・OKLCH` |

---

## Penpot MCP API build sequence

1. **Root frame** — create board, flex column, padding 32px, fill `#FFFFFF`, auto-sizing.
2. **`_colors・do not edit any layer`** — inner board, flex column, rowGap 16px, no fill, hSizing/vSizing auto. Append to root.
3. **`_title`** — board, flex row, justifyContent `space-between`, hSizing fill, vSizing auto. Append to `_colors`.
   - Left: `_palette-global` → `_name` → `_text` (palette name, 20px 500).
   - Right: `_palette-props` → one board per prop row, each containing `_text` (12px 500). `_provider` also contains `_avatar` ellipse 24×24 with image fill.
4. **`_shades`** — board, flex column, no gaps. Append to `_colors`.
   - `_header` row (48px): "Couleurs sources" cell + one cell per shade step, each 200px wide, padding 8px. Inside each: `_property > _label > _text`.
   - For each color family, create a **color row** board (flex row, 300px height):
     - `_source` (200px, auto): contains `<colorName>` board (200×300, fill = source color, flex col, pad 8, justifyContent end, rowGap 8) containing `_property > _label > _text`.
     - `_shades` container (flex row): one **shade cell** per step (200×300, fill = shade hex, flex col, pad 8, justifyContent end, rowGap 8):
       - `_properties` (fill+fill, flex col, justifyContent space-between, alignItems stretch):
         - `_top` (fill+auto, flex row): `_scale` (auto, pad 4/8, fill #FFFFFF 50%) + `_base` (fill+auto, flex col rowGap 4, alignItems end) → `_hex`, `_oklch`.
         - `_bottom` (fill+auto, flex col): `_contrast-scores` (flex col, rowGap 4) → 4 rows (wcag21-light, apca-light, wcag21-dark, apca-dark), each flex row colGap 4 with ellipse 8×8, ratio text, and score badge (auto, pad 4/8, borderRadius 16).
5. **`_signature`** — board, flex row, justifyContent space-between, hSizing fill. Append to `_colors`.
   - Left: `_info` (flex col, rowGap 4) → `_tagline > _text` (Martian Mono 10px) + `_url > _text` (Lexend 8px).
   - Right: `_logotype` board containing the SVG vector.
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
| Source column header | i18n label from `PaletteData` (e.g. `Couleurs sources`) |
| Shade column header | `<scale>` (e.g. `80`) |
| Color row | `<color name>` (e.g. `Primary`) |
| Source outer frame | `_source` |
| Source inner frame | `<color name>` (same as row name) |
| Source/header label container | `_property > _label > _text` |
| Shades container | `_shades` |
| Shade cell | `<scale>` (e.g. `80`) |
| Shade internals | `_properties > _top / _bottom` |
| Scale badge | `_scale` |
| Color values | `_base > _hex`, `_base > _oklch` |
| Score section | `_contrast-scores` |
| Score rows | `_wcag21-light`, `_apca-light`, `_wcag21-dark`, `_apca-dark` |
| Score indicator | `_indicator` |
| Score badge | `_wcag21-light-score`, `_apca-light-score`, `_wcag21-dark-score`, `_apca-dark-score` |
| Signature | `_signature > _info`, `_signature > _logotype` |
