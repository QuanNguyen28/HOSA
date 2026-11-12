---
name: ui-color-palette-penpot-extract-source-colors
description: Extract solid fill colors from the current Penpot selection and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [selection]
---

# Extract Source Colors from Penpot

Use this skill when the user wants to seed a palette from colors already in their Penpot file — selected shapes, frames, or components.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 0 — Read the Penpot API overview

Before executing any code, call `high_level_overview` to confirm the current API surface for fills and selection. Use `penpot_api_info` if you need the precise shape type or fill property names.

---

## Step 1 — Ensure a selection exists

Before calling any tool, confirm that the user has shapes selected in Penpot.

> Please select one or more shapes in Penpot (rectangles, frames, components, or text) — I'll extract their fill colors.

If the script returns an empty array, ask the user to make a selection and try again.

---

## Step 2 — Extract fills via code execution

**Tool**: `execute_code`

Run the following code to collect all solid fill colors from the current selection:

```js
const shapes = penpot.selection
const seen = new Set()
const colors = []

function extractFills(shape) {
  if (shape.fills) {
    shape.fills.forEach(fill => {
      if (fill.fillType === 'solid' && fill.fillColor) {
        const hex = fill.fillColor.toLowerCase()
        if (!seen.has(hex)) {
          seen.add(hex)
          colors.push({ hex, opacity: fill.fillOpacity ?? 1 })
        }
      }
    })
  }
  if (shape.children) { shape.children.forEach(extractFills) }
}

shapes.forEach(extractFills)
return colors
```

The script recurses into frames and groups. `fillColor` is a hex string; `fillOpacity` is 0–1.

---

## Step 3 — Filter and show colors

From the returned array:
- Skip entries where `opacity < 0.1` (nearly invisible).
- Present the remaining colors as swatches with hex values.

Ask the user to:
- Assign a role name to each color to keep (`primary`, `neutral`, `accent`, `error`, or a custom name)
- Discard colors they do not want

> Found 4 unique fill colors:
>   #3B82F6 — assign a role? (e.g. primary, neutral, accent)
>   #6B7280 — assign a role?
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

- Select shapes that represent the core visual identity of the design (backgrounds, buttons, icons).
- Gradient fills and image fills are skipped — only `solid` fills are extracted.
- The script recurses into frames and groups automatically; selecting a top-level frame captures all nested colors.
- Colors extracted from a Penpot file already represent design intent — keep 3–5 max.
- If `penpot.selection` is empty but the user reports a selection, check if the plugin context matches the active page.
