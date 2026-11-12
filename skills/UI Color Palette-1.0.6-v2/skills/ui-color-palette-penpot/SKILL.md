---
name: ui-color-palette-penpot
description: Entry point for UI Color Palette workflows targeting Penpot. Use to choose between tokens, styles, and board/document preview generation.
argument-hint: <tokens|styles|preview>
---

# UI Color Palette Penpot

Use this folder as the platform entry point for all **UI Color Palette → Penpot** workflows.

## Folder structure

- `SKILL.md` at the root is the platform index
- `references/` contains the detailed operational sub-skills

## Reuse rule

**Before calling any MCP tool**, check whether `PaletteData` is already present in the conversation context.

If it is, use it directly — **never call `get_palette` again**. Confirm to the user:

> Using the palette already built in this session. Generating Penpot artifacts now.

Only rebuild the palette if the user explicitly asks to change colors, preset, or themes.

---

## Structure-first rule

This platform skill is primarily a routing and orchestration layer.

The agent should:

1. identify whether the user needs tokens, styles, or preview first
2. choose the matching file in `references/`
3. normalize the palette payload for that workflow
4. only then translate the workflow into MCP or plugin API operations

Do not start from raw API calls. Start from the workflow structure.

## Available sub-skills

- `references/extract-source-colors.md` — extract solid fill colors from the current Penpot selection to seed a palette
- `references/extract-styles-colors.md` — extract colors from the Penpot local color library to seed a palette
- `references/generate-tokens.md` — generate or sync Penpot local **primitive** tokens and themed sets
- `references/generate-semantic-tokens.md` — generate or sync Penpot **semantic** token sets from `SystemData` (reference layer on top of primitives)
- `references/generate-styles.md` — generate or sync Penpot local color styles
- `references/generate-preview.md` — draw the palette as a swatch board on the Penpot canvas (canvas rendering only, not token/style export)

## Routing

Choose the sub-skill by user intent:

- “extract colors from selection”, “pick colors from selection”, “colors from Penpot” → `references/extract-source-colors.md`
- “extract colors from library”, “local colors”, “color library”, “seed from styles” → `references/extract-styles-colors.md`
- “tokens”, “primitive colors”, “theme tokens”, “Penpot token sets” → `references/generate-tokens.md`
- “semantic tokens”, “color system tokens”, “system token set”, `SystemData` present in context → `references/generate-semantic-tokens.md`
- “styles”, “local colors”, “style library”, “swatches” → `references/generate-styles.md`
- “full handoff”, “everything in Penpot”, “tokens + styles + preview” → primitives first (`references/generate-tokens.md`), semantics if `SystemData` is available (`references/generate-semantic-tokens.md`), then styles (`references/generate-styles.md`), then preview (`references/generate-preview.md`)
- “preview”, “board”, “document review”, “swatch board”, “canvas rendering”, “visual board” → `references/generate-preview.md`

When routing a `SystemData`-based workflow to `references/generate-semantic-tokens.md`, pass `SystemData` and `PaletteData` opaquely. The sub-skill:
- **First** ensures the palette's primitive token sets exist (mandatory prerequisite for reference resolution)
- Creates one semantic token set per theme, named `systemName/themeName` (or `systemName` for no-theme systems)
- Adds one **token** per entry in `SystemData.tokens`, named by joining `token.pathNames` with `.`
- Each token value references the primitive token as `{colorName_snake.shadeName}` (resolved via `token.refs[themeIndex].shadeId`)
- Excluded tokens (`isExcluded: true`) and unbound refs (`shadeId: null`) are skipped
## Platform API references

An agent should think in terms of the Penpot plugin/API surface, not only the plugin wrapper:

- **Local token catalog API**
  - token sets
  - tokens
  - themes and theme groups
- **Local style/color API**
  - local library colors
  - style path, name, color, opacity
- **Document API**
  - boards/documents
  - node creation and update
  - plugin data on current page/document

## MCP usage strategy

Use MCP or direct API calls as the execution layer, not as the skill structure.

- The root skill chooses the workflow.
- The reference file defines the expected inputs, transformations, and outputs.
- MCP/API calls execute the chosen workflow.

## Agent rule

The plugin bridge files are reference implementations. If the plugin action is unavailable, the agent should reproduce the same behavior directly through Penpot API requests.

---

## Recommended subagent

Delegate this skill to **`palette-transitioner`**.

The `palette-transitioner` agent normalizes `PaletteData` into the correct row model for Penpot (`tokenRows`, `styleRows`, `previewRows`), then routes execution through the appropriate Penpot sub-skill.
