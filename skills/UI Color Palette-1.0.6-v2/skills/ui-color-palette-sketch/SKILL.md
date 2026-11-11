---
name: ui-color-palette-sketch
description: Entry point for UI Color Palette workflows targeting Sketch. Use to choose between swatches, shared styles, and document preview generation.
argument-hint: <variables|styles|tokens|preview>
---

# UI Color Palette Sketch

Use this folder as the platform entry point for all **UI Color Palette → Sketch** workflows.

## Folder structure

- `SKILL.md` at the root is the platform index
- `references/` contains the detailed operational sub-skills

## Reuse rule

**Before calling any MCP tool**, check whether `PaletteData` is already present in the conversation context.

If it is, use it directly — **never call `get_palette` again**. Confirm to the user:

> Using the palette already built in this session. Generating Sketch artifacts now.

Only rebuild the palette if the user explicitly asks to change colors, preset, or themes.

---

## Structure-first rule

This platform skill is primarily a routing and orchestration layer.

The agent should:

1. identify whether the user needs swatches, shared styles, or preview first
2. choose the matching file in `references/`
3. normalize the palette payload for that workflow
4. only then translate the workflow into MCP or plugin API operations

Do not start from raw API calls. Start from the workflow structure.

## Available sub-skills

- `references/extract-source-colors.md` — extract solid fill colors from the current Sketch selection to seed a palette
- `references/extract-styles-colors.md` — extract solid fill colors from Sketch shared layer styles to seed a palette
- `references/generate-variables.md` — generate or sync Sketch **primitive** swatches
- `references/generate-semantic-variables.md` — generate or sync Sketch **semantic** swatches from `SystemData` (taxonomy-named swatches with resolved hex values, one per theme)
- `references/generate-styles.md` — generate or sync Sketch shared layer styles
- `references/generate-preview.md` — draw the palette as a swatch board on the Sketch canvas (canvas rendering only, not swatch/style export)

## Routing

Choose the sub-skill by user intent:

- “extract colors from selection”, “pick colors from selection”, “colors from Sketch” → `references/extract-source-colors.md`
- “extract colors from styles”, “shared styles”, “style library”, “seed from styles” → `references/extract-styles-colors.md`
- “variables”, “swatches”, “color variables”, “primitive colors” → `references/generate-variables.md`
- “semantic swatches”, “color system swatches”, “system swatch set”, `SystemData` present in context → `references/generate-semantic-variables.md`
- “styles”, “shared styles”, “reusable fills” → `references/generate-styles.md`
- “full Sketch setup”, “tokens”, “preview + styles + swatches” → primitives first (`references/generate-variables.md`), semantics if `SystemData` is available (`references/generate-semantic-variables.md`), then styles (`references/generate-styles.md`), then preview (`references/generate-preview.md`)
- “preview”, “swatch board”, “canvas rendering”, “visual board” → `references/generate-preview.md`

When routing a `SystemData`-based workflow to `references/generate-semantic-variables.md`, pass `SystemData` and `PaletteData` opaquely. The sub-skill:
- **First** ensures primitive swatches exist (mandatory to guarantee PaletteData consistency)
- Creates one swatch per theme per token, named `systemName/themeName/tokenPath`
- Swatch value is a **raw hex** resolved from `token.refs[i].shadeId` via PaletteData — Sketch has no alias or reference mechanism
- Excluded tokens (`isExcluded: true`) and unbound refs (`shadeId: null`) are skipped

An agent should think in terms of the Sketch plugin/document API surface, not only the plugin wrapper:

- **Document color API**
  - document swatches
  - add/remove/update swatches
- **Shared style API**
  - shared layer styles
  - style fills and names
- **Document structure API**
  - pages, layers, groups, artboards
  - document settings and layer settings
  - create/update preview boards or sheets

## MCP usage strategy

Use MCP or direct API calls as the execution layer, not as the skill structure.

- The root skill chooses the workflow.
- The reference file defines the expected inputs, transformations, and outputs.
- MCP/API calls execute the chosen workflow.

## Agent rule

The plugin bridge files are reference implementations. If the plugin action is unavailable, the agent should reproduce the same behavior directly through Sketch API requests.

---

## Recommended subagent

Delegate this skill to **`palette-transitioner`**.

The `palette-transitioner` agent normalizes `PaletteData` into the correct row model for Sketch (`swatchRows`, `styleRows`, `previewRows`), then routes execution through the appropriate Sketch sub-skill.
