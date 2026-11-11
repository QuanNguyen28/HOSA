---
name: ui-color-palette-figma
description: Entry point for UI Color Palette workflows targeting Figma. Use to choose between variables and styles generation.
argument-hint: <variables|styles>
---

# UI Color Palette Figma

Use this folder as the platform entry point for all **UI Color Palette → Figma** workflows.

Figma does not have a native token format. The canonical artifacts in Figma are:

- **Variables** — the primary token system (modes, themes, value bindings)
- **Styles** — the visual/application layer (paint styles, swatch reuse)

For design token formats (DTCG, Style Dictionary, etc.), use `ui-color-palette-generate-code` instead.

## Folder structure

- `SKILL.md` at the root is the platform index
- `references/` contains the detailed operational sub-skills

## Reuse rule

**Before calling any MCP tool**, check whether `PaletteData` is already present in the conversation context.

If it is, use it directly — **never call `get_palette` again**. Confirm to the user:

> Using the palette already built in this session. Generating Figma artifacts now.

Only rebuild the palette if the user explicitly asks to change colors, preset, or themes.

---

## Structure-first rule

This platform skill is primarily a routing and orchestration layer.

The agent should:

1. identify which artifact the user wants first
2. choose the matching file in `references/`
3. normalize the palette payload for that workflow
4. only then translate the workflow into MCP or plugin API operations

Do not start from raw API calls. Start from the workflow structure.

## Available sub-skills

- `references/extract-source-colors.md` — extract solid fill colors from the current Figma selection to seed a palette
- `references/extract-styles-colors.md` — extract solid fill colors from Figma paint styles to seed a palette
- `references/generate-variables.md` — generate or sync Figma local **primitive** variables and modes
- `references/generate-semantic-variables.md` — generate or sync Figma **semantic** variable collection from `SystemData` (VariableAlias layer on top of primitives)
- `references/generate-styles.md` — generate or sync Figma local paint styles
- `references/generate-preview.md` — draw the palette as a swatch board on the Figma canvas (canvas rendering only, not variable/style export)

## Routing

Choose the sub-skill by user intent:

- "extract colors from selection", "pick colors from selection", "colors from Figma" → `references/extract-source-colors.md`
- "extract colors from styles", "colors from paint styles", "seed from style library" → `references/extract-styles-colors.md`
- "variables", "modes", "theme variables", "primitive colors" → `references/generate-variables.md`
- "semantic variables", "color system variables", "system variable collection", `SystemData` present in context → `references/generate-semantic-variables.md`
- "paint styles", "local styles", "style library", "swatches" → `references/generate-styles.md`
- "full handoff", "everything in Figma", "variables + styles + preview" → primitives first (`references/generate-variables.md`), semantics if `SystemData` is available (`references/generate-semantic-variables.md`), then styles (`references/generate-styles.md`), then preview (`references/generate-preview.md`)
- "preview", "swatch board", "canvas rendering", "visual board" → `references/generate-preview.md`

When routing a `SystemData`-based workflow to `references/generate-semantic-variables.md`, pass `SystemData` and `PaletteData` opaquely. The sub-skill:
- **First** ensures the palette's primitive variable collection exists (mandatory prerequisite for alias resolution)
- Creates one semantic Figma variable collection named after the system schema or user-supplied label
- Adds one **mode** per theme, mirroring the primitive collection's mode structure
- Adds one **variable** per token in `SystemData.tokens`, named by joining `token.pathNames` with `/`
- Sets each variable's value per mode as a **VariableAlias** pointing to the corresponding primitive variable (resolved via `token.refs[themeIndex].shadeId`)
- Excluded tokens (`isExcluded: true`) and unbound refs (`shadeId: null`) are skipped

If the user asks for "tokens" in the context of Figma, clarify that Figma does not have a native token format and route to variables instead. If they want exportable design tokens, route to `ui-color-palette-generate-code`.

## Platform API references

An agent should think in terms of the Figma Plugin API surface, not only the plugin wrapper:

- **Variables API**
  - local variable collections
  - collection modes
  - local variables
  - set value for mode
- **Styles API**
  - local paint styles
  - style name and description
  - solid paint fills and opacity
- **Document / node API**
  - frames, sections, groups, text nodes
  - plugin data on nodes
  - create/update preview boards

## MCP usage strategy

Use MCP or direct API calls as the execution layer, not as the skill structure.

- The root skill chooses the workflow.
- The reference file defines the expected inputs, transformations, and outputs.
- MCP/API calls execute the chosen workflow.

## Agent rule

The plugin bridge files are reference implementations. If the plugin action is unavailable, the agent should reproduce the same behavior directly through Figma API requests.

---

## Recommended subagent

Delegate this skill to **`palette-transitioner`**.

The `palette-transitioner` agent normalizes `PaletteData` into the correct row model for Figma (`variableRows`, `styleRows`, `previewRows`), then routes execution through the appropriate Figma sub-skill.
