---
name: ui-color-palette-generate-source-colors
description: Generate source colors to seed a palette. Supports three modes — extract dominant colors from an image, generate from a natural language prompt, or derive harmonies from a base color. Output is a set of ColorConfiguration objects ready to pass to ui-color-palette-scale-palette.
argument-hint: <image|prompt|harmony> [input]
---

# Generate Source Colors

Use the **ui-color-palette** MCP tools to produce source colors before building a full palette.

The output of this skill is a set of `ColorConfiguration` objects (role name + hex) ready to be passed to `ui-color-palette-scale-palette`.

---

## Step 0 — Check for existing SourceColors

**Before asking anything**, check whether a `SourceColors` slot is already populated in the conversation context.

If `SourceColors` exists, show the existing colors (name + hex) and ask: reuse, add more, or start fresh. Wait for reply before proceeding.

---

## Step 1 — Choose a source mode

If the mode is not already clear from context, ask which source to use:

- **Image** — extract dominant colors from a photo (requires public URL)
- **Prompt** — describe mood/brand in natural language
- **Harmony** — derive from a single base color
- **Design tool** — extract fills from a current selection in Figma, Penpot, Sketch, or Framer

Wait for reply.

---

## Mode A — Image extraction

**Tool**: `extract_dominant_colors`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `imageUrl` | string | Yes | Public URL of a JPEG or PNG image |
| `colorCount` | number | No | Number of dominant colors to extract (default: 5) |
| `maxIterations` | number | No | Max iterations for k-means clustering |
| `tolerance` | number | No | Convergence tolerance |
| `skipTransparent` | boolean | No | Skip transparent pixels (default: true) |

### Step A1 — Collect the image URL

Ask for a public JPEG or PNG URL if not already provided.

### Step A2 — Color count (optional)

Ask how many dominant colors to extract (default: 5).

### Step A3 — Call `extract_dominant_colors`

Call the tool with the URL and parameters. The tool returns colors as hex and/or RGB (0–255 per channel).

### Step A4 — Show results and assign roles

Show the extracted colors as swatches (hex + preview). Ask the user to assign a role name (`primary`, `neutral`, `accent`, `error`) to each color they want to keep, and discard the rest.

### Step A5 — Normalize to ColorConfiguration

Convert each kept color to a `ColorConfiguration` object:
- `id` = omit — the server generates it automatically via `uid()`
- `name` = the role name the user provided
- `rgb` = divide each 0–255 channel by 255 → `{ r: R/255, g: G/255, b: B/255 }`
- Apply defaults: `hue: { shift: 0, isLocked: false }`, `chroma: { shift: 100, isLocked: false }`, `alpha: { isEnabled: false, backgroundColor: "#FFFFFF" }`

---

## Mode B — Prompt generation

**Tool**: `generate_colors_from_prompt`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `prompt` | string | Yes | Natural language description of the desired palette |

### Step B1 — Collect the prompt

Ask for a natural language description if not already provided (mood, brand, context, or specific colors; e.g. "a calm fintech app with deep blues and warm neutrals").

### Step B2 — Call `generate_colors_from_prompt`

Call the tool with the prompt string. The tool uses AI (Mistral) to return a set of colors.

### Step B3 — Show results and assign roles

Show the suggested colors as swatches. Ask the user to assign a role name to each color they want to keep and discard the rest.

### Step B4 — Normalize to ColorConfiguration

Convert each kept color to a `ColorConfiguration` object using the same mapping as Step A5.

---

## Mode C — Harmony derivation

**Tool**: `create_color_harmony`

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `baseColor` | array | Yes | An RGB Channel tuple: `[r, g, b]` — values 0–255 |
| `type` | enum | No | `ALL`, `COMPLEMENTARY`, `ANALOGOUS`, `TRIADIC`, `TETRADIC`, `SQUARE`, `COMPOUND` (default: `ALL`) |
| `analogousSpread` | number | No | Spread angle in degrees for analogous harmonies (default: 30) |
| `returnFormat` | enum | No | `rgb`, `hex`, or `both` (default: `both`) |

### Step C1 — Collect the base color

Ask for a hex base color if not already provided. Convert to an RGB Channel tuple:
- Parse hex → `[r, g, b]` with values 0–255
- Example: `#3B82F6` → `[59, 130, 246]`

### Step C2 — Choose harmony type

Ask which harmony type: Complementary (2 colors), Compound (3), Analogous (3), Triadic (3), Tetradic (4), Square (4), or All.

### Step C3 — Call `create_color_harmony`

Call the tool with the Channel object, selected type, and `returnFormat: "both"`.

### Step C4 — Show results and assign roles

Show harmony colors as swatches (grouped by type if `ALL`). Ask the user to pick and assign a role name to each color they want to keep.

### Step C5 — Normalize to ColorConfiguration

Convert each kept color to a `ColorConfiguration` object using the same mapping as Step A5.

---

## Output

Once role names are confirmed, present the final source color set as a readable list:

```
Source colors ready:

  primary   #3B82F6
  neutral   #6B7280
  accent    #F59E0B
```

**Session state**: Store this result as the `SourceColors` slot. It will be reused automatically by `ui-color-palette-scale-palette` — the user will not need to re-enter the colors.

Then hand off to `ui-color-palette-scale-palette` to build the full palette.

---

---

## Mode D — Design tool selection

Route to the matching design-tool reference file based on which tool the user has open and whether they want colors from the **current selection** or from the **styles/library**.

| Tool | From selection | From styles / library |
| ---- | -------------- | --------------------- |
| Figma | `ui-color-palette-figma/references/extract-source-colors.md` | `ui-color-palette-figma/references/extract-styles-colors.md` |
| Penpot | `ui-color-palette-penpot/references/extract-source-colors.md` | `ui-color-palette-penpot/references/extract-styles-colors.md` |
| Sketch | `ui-color-palette-sketch/references/extract-source-colors.md` | `ui-color-palette-sketch/references/extract-styles-colors.md` |
| Framer | `ui-color-palette-framer/references/extract-source-colors.md` | `ui-color-palette-framer/references/extract-styles-colors.md` |

If the source (selection vs styles) is ambiguous, ask: "Should I extract from your current selection, or from the file's style library / local colors?"

If the tool is not specified, ask: "Which design tool are you working in — Figma, Penpot, Sketch, or Framer?"

Each reference file handles the tool-specific extraction and normalizes the result to `ColorConfiguration` objects using the same Step A5 mapping. The role assignment and `SourceColors` slot storage are also handled there.

---

## Tips

- **Combine modes**: e.g. extract from a design tool selection, then harmonize one of the extracted colors with Mode C.
- **Hex conversions**: Channel tuple → `[r, g, b]` 0–255 (e.g. `#3B82F6` → `[59, 130, 246]`); rgb 0–1 → divide by 255 (e.g. `{ r: 0.23, g: 0.51, b: 0.96 }`).
- **Color count**: 2–5 ideal (1 primary, 1 neutral, ≤3 accents/semantics). Image URL must be publicly accessible (no auth, no CORS).
- **Design tool extraction**: only solid fills are extracted — gradients and image fills are skipped. Select diverse layers for better coverage.

## Arguments

`$ARGUMENTS` can specify the source mode directly:

- `/ui-color-palette:generate-source-colors image` — jump straight to image URL prompt
- `/ui-color-palette:generate-source-colors prompt warm sunset palette` — use the rest as the prompt
- `/ui-color-palette:generate-source-colors harmony #3B82F6` — use the hex as the base color
- `/ui-color-palette:generate-source-colors figma` — extract from current Figma selection
- `/ui-color-palette:generate-source-colors figma styles` — extract from Figma paint styles
- `/ui-color-palette:generate-source-colors penpot` — extract from current Penpot selection
- `/ui-color-palette:generate-source-colors penpot styles` — extract from Penpot local color library
- `/ui-color-palette:generate-source-colors sketch` — extract from current Sketch selection
- `/ui-color-palette:generate-source-colors sketch styles` — extract from Sketch shared layer styles
- `/ui-color-palette:generate-source-colors framer` — extract from current Framer selection
- `/ui-color-palette:generate-source-colors framer styles` — extract from Framer color styles
