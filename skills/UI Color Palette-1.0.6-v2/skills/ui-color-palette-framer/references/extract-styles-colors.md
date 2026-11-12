---
name: ui-color-palette-framer-extract-styles-colors
description: Extract colors from Framer local color styles and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [styles]
---

# Extract Source Colors from Framer Color Styles

Use this skill when the user wants to seed a palette from **existing Framer color styles** — the local color styles defined in the project.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 1 — Fetch the project structure

**Tool**: `getProjectXml`

This returns the full project structure including pages, components, and **styles**. Color styles appear in a `<styles>` section (or equivalent) within the project XML.

---

## Step 2 — Extract color styles from the XML

Parse the returned XML to find color style entries. Look for:

- Elements or attributes that define color styles (typically `<colorStyle>`, `<style type="color">`, or similar)
- Each entry typically carries a `name`/`path` and a `light` color value (and optionally `dark`)
- Color values are in CSS format: hex (`#RRGGBB`), `rgb(…)`, or `rgba(…)`

For each color style found:
1. Extract `name` (or `path`) and `light` color value.
2. Normalize the color to hex (see helpers below).
3. Skip transparent values (`rgba(…, 0)` or `opacity: 0`).
4. Deduplicate by normalized hex.

### Color normalization helpers

- 3-digit hex → 6-digit: `#RGB` → `#RRGGBB`
- `rgb(r, g, b)` → hex: `Math.round(r).toString(16).padStart(2,'0')` per channel
- `rgba(r, g, b, a)` → use hex of RGB part; note opacity separately

---

## Step 3 — Show colors and assign roles

Present the deduplicated colors as swatches, using the style name/path as a role suggestion. Ask the user to:
- Confirm or rename the suggested role for each color to keep
- Discard colors they do not want

> Found 4 color styles:
>   /Brand/Primary   #3B82F6 — role? (suggested: primary)
>   /Neutral/500     #6B7280 — role? (suggested: neutral)
>   …

---

## Step 4 — Normalize to ColorConfiguration

For each kept color, parse the hex to RGB 0–1 and produce a `ColorConfiguration` object:

```json
{
  "name": "<role name>",
  "description": "",
  "rgb": { "r": <r/255>, "g": <g/255>, "b": <b/255> },
  "hue": { "shift": 0, "isLocked": false },
  "chroma": { "chroma": 100, "isLocked": false },
  "alpha": { "isEnabled": false, "backgroundColor": "#FFFFFF" }
}
```

Do not set `id`.

### Hex → RGB 0–1

```
r = parseInt(hex.slice(1,3), 16) / 255
g = parseInt(hex.slice(3,5), 16) / 255
b = parseInt(hex.slice(5,7), 16) / 255
```

---

## Step 5 — Hand off

Store the result as the `SourceColors` slot and hand off to `ui-color-palette-scale-palette`.

---

## Tips

- Framer color style paths (`/Brand/Primary`) carry semantic meaning — use the last path segment as a role suggestion.
- If the project XML does not clearly expose color styles, fall back to `extract-source-colors.md` (selection-based) or ask the user to provide hex values directly.
- Only `light` values are used for source color extraction — `dark` values are ignored at this stage (they inform the semantic system later via `SystemData`).
- If the project has many styles (20+), ask the user to pick the most representative ones rather than keeping all.
