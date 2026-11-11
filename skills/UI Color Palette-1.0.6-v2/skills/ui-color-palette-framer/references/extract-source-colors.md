---
name: ui-color-palette-framer-extract-source-colors
description: Extract fill colors from the current Framer selection and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [selection]
---

# Extract Source Colors from Framer

Use this skill when the user wants to seed a palette from colors already in their Framer project — selected frames, stacks, or components.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 0 — Ensure a selection exists

Before calling any tool, confirm that the user has nodes selected in Framer.

> Please select one or more nodes in Framer (frames, stacks, components, or shapes) — I'll extract their fill colors.

If `getSelectedNodesXml` returns an empty result or no color attributes are found, ask the user to make a selection and try again.

---

## Step 1 — Get the selection as XML

**Tool**: `getSelectedNodesXml`

This returns the selected nodes as an XML string. Each node may carry color information in attributes such as `background`, `fill`, `color`, `backgroundColor`, or inline style strings.

---

## Step 2 — Extract colors from the XML

Parse the returned XML string to find color values. Look for:

- Attribute values matching CSS hex format: `#[0-9a-fA-F]{3,8}`
- Attribute values matching `rgb(…)` or `rgba(…)` patterns
- Attribute names that commonly carry fill colors: `background`, `fill`, `backgroundColor`, `color`, `borderColor`

Ignore:
- Colors with `rgba(…, 0)` or fully transparent values
- Pure black (`#000000`, `rgb(0,0,0)`) and pure white (`#FFFFFF`, `rgb(255,255,255)`) unless they are explicitly meaningful in context (ask the user)
- Gradient or image fill references

Deduplicate by normalized hex value.

### Normalization helpers

- 3-digit hex → 6-digit: `#RGB` → `#RRGGBB`
- `rgb(r, g, b)` → hex: `Math.round(r).toString(16).padStart(2,'0')` per channel
- `rgba(r, g, b, a)` → hex (ignore alpha) + note the opacity

---

## Step 3 — Show colors and assign roles

Present the deduplicated colors as swatches with their hex values. Ask the user to:
- Assign a role name to each color to keep (`primary`, `neutral`, `accent`, `error`, or a custom name)
- Discard colors they do not want

> Found 3 unique fill colors:
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

- Select nodes that represent the core visual identity of the design (hero sections, buttons, cards).
- Framer's XML may encode colors in multiple formats — apply all regex patterns to avoid missing values.
- If the XML is large and contains many incidental colors, show only the top 8–10 most frequent ones and ask the user to pick.
- Colors extracted from a Framer project already represent design intent — keep 3–5 max.
- If color extraction from XML yields poor results, fall back to a screenshot approach: ask the user to provide a screenshot URL and use `extract_dominant_colors` from the `ui-color-palette` MCP (Mode A of `ui-color-palette-generate-source-colors`).
