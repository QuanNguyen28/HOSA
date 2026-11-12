---
name: ui-color-palette-sketch-extract-styles-colors
description: Extract solid fill colors from Sketch shared layer styles and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [styles]
---

# Extract Source Colors from Sketch Styles

Use this skill when the user wants to seed a palette from **existing Sketch shared layer styles** — the reusable fill styles defined in the document.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 1 — Extract fills from shared styles

**Tool**: `run_code`

Run the following script to collect solid fill colors from all shared layer styles:

```js
const sketch = require('sketch')
const doc = sketch.getSelectedDocument()
const colors = []
const seen = new Set()
doc.sharedLayerStyles.forEach(sharedStyle => {
  const name = sharedStyle.name
  if (sharedStyle.style && sharedStyle.style.fills) {
    sharedStyle.style.fills.forEach(fill => {
      if (fill.fillType === 'Color' && fill.enabled !== false) {
        const c = fill.color
        const hex = c.toString()
        if (!seen.has(hex)) {
          seen.add(hex)
          colors.push({ name, hex, r: c.red, g: c.green, b: c.blue })
        }
      }
    })
  }
})
console.log(JSON.stringify(colors))
```

Each entry includes the style name, hex, and RGB 0–1 channels.

---

## Step 2 — Show colors and assign roles

Parse the JSON output. Present the deduplicated colors as swatches, using the shared style name as a role suggestion. Ask the user to:
- Confirm or rename the suggested role for each color to keep
- Discard colors they do not want

> Found 4 shared layer styles with solid fills:
>   Backgrounds/Primary   #3B82F6 — role? (suggested: primary)
>   Text/Muted            #6B7280 — role? (suggested: neutral)
>   …

---

## Step 3 — Normalize to ColorConfiguration

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

`r`, `g`, `b` from Sketch are already 0–1 — use them directly. Do not set `id`.

---

## Step 4 — Hand off

Store the result as the `SourceColors` slot and hand off to `ui-color-palette-scale-palette`.

---

## Tips

- Shared style names often carry semantic meaning (`Backgrounds/Primary`, `Text/Muted`) — use them as role suggestions.
- If the document has many styles (20+), ask the user to pick the most representative ones.
- Only solid fills are extracted — gradient and pattern fills are skipped.
- To also extract from document swatches (not shared styles), replace `sharedLayerStyles` with `colors` in the script: `doc.colors.forEach(c => { ... })`.
