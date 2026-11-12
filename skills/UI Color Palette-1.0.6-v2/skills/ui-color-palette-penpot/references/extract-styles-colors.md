---
name: ui-color-palette-penpot-extract-styles-colors
description: Extract colors from the Penpot local color library and normalize them into ColorConfiguration objects. Use as a source mode before building a palette with ui-color-palette-scale-palette.
argument-hint: [styles]
---

# Extract Source Colors from Penpot Color Library

Use this skill when the user wants to seed a palette from **existing Penpot local colors** — colors defined in the file's local library.

This produces `ColorConfiguration` objects ready to pass to `ui-color-palette-scale-palette`.

---

## Step 0 — Read the Penpot API overview

Call `high_level_overview` before executing any code to confirm the current API surface for local library colors. Use `penpot_api_info` if you need the precise property names.

---

## Step 1 — Extract local library colors

**Tool**: `execute_code`

Run the following code to collect all colors from the local library:

```js
const colors = []
const seen = new Set()
const localColors = penpot.library.local.colors
localColors.forEach(color => {
  const hex = (color.color ?? '#000000').toLowerCase()
  if (!seen.has(hex)) {
    seen.add(hex)
    colors.push({ name: color.name, hex, opacity: color.opacity ?? 1 })
  }
})
return colors
```

Each entry includes the color name, hex value, and opacity.

---

## Step 2 — Filter and show colors

From the returned array:
- Skip entries where `opacity < 0.1`.
- Present the remaining colors as swatches, using the library color name as a role suggestion.

Ask the user to:
- Confirm or rename the suggested role for each color to keep
- Discard colors they do not want

> Found 5 local library colors:
>   Brand/Blue     #3B82F6 — role? (suggested: primary)
>   Neutral/Gray   #6B7280 — role? (suggested: neutral)
>   …

---

## Step 3 — Normalize to ColorConfiguration

For each kept color, parse hex to RGB 0–1 and produce a `ColorConfiguration` object:

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

## Step 4 — Hand off

Store the result as the `SourceColors` slot and hand off to `ui-color-palette-scale-palette`.

---

## Tips

- Local library color names in Penpot often reflect semantic roles (`Brand/Blue`, `Neutral/Gray`) — use them as role suggestions.
- If the library has many colors (20+), ask the user to pick the most representative ones.
- If `penpot.library.local.colors` is empty but the user expects colors, check whether they are in a shared library — try `penpot.library.connected` for connected libraries.
- Use `penpot_api_info` to confirm the exact property path if the API surface has changed.
