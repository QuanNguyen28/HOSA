---
name: ui-color-palette-sketch-extract-source-colors
description: Extract solid fill colors from the current Sketch selection and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [selection]
---

# Extract Source Colors from Sketch

Use this skill when the user wants to seed a palette from colors already in their Sketch document — selected layers, artboards, or symbols.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 0 — Ensure a selection exists

Before calling any tool, confirm that the user has layers selected in Sketch.

> Please select one or more layers in Sketch (shapes, artboards, symbols, or text) — I'll extract their fill colors.

If the script returns an empty array, ask the user to make a selection and try again.

---

## Step 1 — Extract fills via script

**Tool**: `run_code`

Run the following script to collect all solid fill colors from the current selection:

```js
const sketch = require('sketch')
const layers = sketch.getSelectedDocument().selectedLayers.layers
const colors = []
function extractFills(layer) {
  if (layer.style && layer.style.fills) {
    layer.style.fills.forEach(fill => {
      if (fill.fillType === 'Color' && fill.enabled !== false) {
        const c = fill.color
        colors.push({ hex: c.toString(), r: c.red, g: c.green, b: c.blue, a: c.alpha })
      }
    })
  }
  if (layer.layers) { layer.layers.forEach(extractFills) }
}
layers.forEach(extractFills)
const unique = [...new Map(colors.map(c => [c.hex, c])).values()]
console.log(JSON.stringify(unique))
```

The script recurses into groups and nested layers. `fill.color` values are in 0–1 range per channel.

---

## Step 2 — Show colors and assign roles

Parse the JSON output. Present the deduplicated colors as swatches with their hex values. Ask the user to:
- Assign a role name to each color to keep (`primary`, `neutral`, `accent`, `error`, or a custom name)
- Discard colors they do not want

> Found 4 unique fill colors:
>   #3B82F6 — assign a role? (e.g. primary, neutral, accent)
>   #6B7280 — assign a role?
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

The `r`, `g`, `b` values from Sketch are already in 0–1 range — use them directly. Do not set `id`.

---

## Step 4 — Hand off

Store the result as the `SourceColors` slot and hand off to `ui-color-palette-scale-palette`.

---

## Alternative — image-based extraction

If the selection is complex (many layers, gradients, images) or the script returns too many colors, use `get_selection_as_image` instead:

1. Call `get_selection_as_image` to capture the selection as a PNG.
2. If the image has a public URL, pass it to `extract_dominant_colors` from the `ui-color-palette` MCP.
3. Follow Mode A of `ui-color-palette-generate-source-colors` from that point.

This approach works well for mood-board style selections or when precise hex values are less important than dominant color impression.

---

## Tips

- Select layers that represent the core visual identity of the design (backgrounds, buttons, icons).
- Gradient fills and image fills are skipped — only solid fills are extracted.
- The script recurses into groups automatically; select a top-level group or artboard to capture all nested colors.
- Colors extracted from a Sketch file already represent design intent — keep 3–5 max.
