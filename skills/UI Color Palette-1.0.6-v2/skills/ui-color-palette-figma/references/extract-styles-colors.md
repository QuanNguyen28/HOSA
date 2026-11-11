---
name: ui-color-palette-figma-extract-styles-colors
description: Extract solid fill colors from Figma paint styles and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [styles]
---

# Extract Source Colors from Figma Styles

Use this skill when the user wants to seed a palette from **existing Figma paint styles** — local color styles defined in the file.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 1 — Fetch all styles

**Tool**: `figma_get_styles`

| Parameter | Value |
| --------- | ----- |
| `verbosity` | `"standard"` — sufficient to get fill colors |
| `enrich` | `false` — not needed for color extraction |

The response includes paint styles (color styles), text styles, effect styles, and grid styles. Focus on **paint styles** only.

---

## Step 2 — Extract solid fills from paint styles

From the response, iterate over paint styles:

1. Filter for styles where `type === "PAINT"` (or equivalent color style type).
2. For each paint style, find fills where `fill.type === "SOLID"`.
3. Extract `fill.color`: `{ r, g, b }` normalized 0–1, plus `fill.opacity` (default 1 if absent).
4. Skip fills with `opacity < 0.1` or `fill.visible === false`.
5. Record the style name alongside the color for role suggestion.

Deduplicate by hex value (convert `{ r, g, b }` to hex, then `new Set()`).

### RGB 0–1 → hex

```
r255 = Math.round(r * 255)
g255 = Math.round(g * 255)
b255 = Math.round(b * 255)
hex = "#" + [r255, g255, b255].map(v => v.toString(16).padStart(2, '0')).join('')
```

---

## Step 3 — Show colors and assign roles

Present the deduplicated colors as swatches, using the style name as a role suggestion. Ask the user to:
- Confirm or rename the suggested role for each color to keep
- Discard colors they do not want

> Found 5 paint styles:
>   Brand/Primary   #3B82F6 — role? (suggested: primary)
>   Neutral/500     #6B7280 — role? (suggested: neutral)
>   …

---

## Step 4 — Normalize to ColorConfiguration

For each kept color, produce a `ColorConfiguration` object:

```json
{
  "name": "<role name>",
  "description": "",
  "rgb": { "r": <r>, "g": <g>, "b": <b> },
  "hue": { "shift": 0, "isLocked": false },
  "chroma": { "chroma": 100, "isLocked": false },
  "alpha": { "isEnabled": false, "backgroundColor": "#FFFFFF" }
}
```

`r`, `g`, `b` are already 0–1 from Figma — use them directly. Do not set `id`.

---

## Step 5 — Hand off

Store the result as the `SourceColors` slot and hand off to `ui-color-palette-scale-palette`.

---

## Tips

- Paint style names often reflect semantic roles (`Brand/Primary`, `Neutral/500`) — use them as role suggestions.
- If the file has many styles (20+), ask the user to pick the most representative ones rather than keeping all.
- Gradient and image fills are skipped — only `SOLID` fills produce source colors.
- For variables instead of styles, use `figma_get_variables` and parse color variable values.
