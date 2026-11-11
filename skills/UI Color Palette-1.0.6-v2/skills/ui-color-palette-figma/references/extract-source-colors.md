---
name: ui-color-palette-figma-extract-source-colors
description: Extract solid fill colors from the current Figma selection and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [verbose]
---

# Extract Source Colors from Figma

Use this skill when the user wants to seed a palette from colors already in their Figma file — selected layers, frames, or components.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 0 — Ensure a selection exists

Before calling any tool, confirm that the user has layers selected in Figma.

> Please select one or more layers in Figma (frames, shapes, components, or text) — I'll extract their fill colors.

If `figma_get_selection` returns an empty array, ask the user to make a selection and try again.

---

## Step 1 — Get the selection with fills

**Tool**: `figma_get_selection`

| Parameter | Value |
| --------- | ----- |
| `verbose` | `true` — required to fetch fills, strokes, and styles per node |

The response includes an array of nodes. Each node may have a `fills` array (when `verbose: true`).

---

## Step 2 — Extract solid fills

From the response, for each node:

1. Access `node.fills` (may be an array or require a secondary `figma_execute` call per node).
2. Filter for fills where `fill.type === "SOLID"`.
3. Extract the color: `{ r, g, b }` already normalized 0–1, plus `fill.opacity` (default 1 if absent).
4. Skip fills with `opacity < 0.1` (nearly invisible) or `fill.visible === false`.

Deduplicate by hex: convert each `{ r, g, b }` to hex (`Math.round(r * 255)` per channel) and remove duplicates.

### RGB 0–1 → hex conversion

```
r255 = Math.round(r * 255)
g255 = Math.round(g * 255)
b255 = Math.round(b * 255)
hex = "#" + r255.toString(16).padStart(2, '0') + g255.toString(16).padStart(2, '0') + b255.toString(16).padStart(2, '0')
```

---

## Step 3 — Show colors and assign roles

Present the deduplicated colors as swatches with their hex values. Ask the user to:
- Assign a role name to each color to keep (`primary`, `neutral`, `accent`, `error`, or a custom name)
- Discard colors they do not want

> Found 4 unique fill colors:
>   #3B82F6 — assign a role? (e.g. primary, neutral, accent)
>   #6B7280 — assign a role?
>   …

---

## Step 4 — Normalize to ColorConfiguration

For each kept color, produce a `ColorConfiguration` object:

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

Do not set `id` — the server generates it automatically.

---

## Step 5 — Hand off

Store the result as the `SourceColors` slot and hand off to `ui-color-palette-scale-palette`.

---

## Tips

- Select diverse layers (backgrounds, buttons, text, icons) to capture the full color range of a design.
- If `verbose: true` does not return fills inline, follow up with a `figma_execute` call to read fills per node id.
- Gradient fills, image fills, and pattern fills are skipped — only `SOLID` fills produce source colors.
- Colors extracted from a Figma file already represent design intent — prefer keeping fewer, higher-meaning colors (3–5 max).
