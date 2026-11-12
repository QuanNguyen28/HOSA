---
name: ui-color-palette-framer
description: Entry point for UI Color Palette workflows targeting Framer. Use to choose between color style synchronization and visual document preview generation.
argument-hint: <styles|tokens|preview>
---

# UI Color Palette Framer

Use this folder as the platform entry point for all **UI Color Palette → Framer** workflows.

## Folder structure

- `SKILL.md` at the root is the platform index
- `references/` contains the detailed operational sub-skills

## Reuse rule

**Before calling any MCP tool**, check whether `PaletteData` is already present in the conversation context.

If it is, use it directly — **never call `get_palette` again**. Confirm to the user:

> Using the palette already built in this session. Generating Framer artifacts now.

Only rebuild the palette if the user explicitly asks to change colors, preset, or themes.

---

## Structure-first rule

This platform skill is primarily a routing and orchestration layer.

The agent should:

1. identify whether the user needs styles or preview first
2. choose the matching file in `references/`
3. normalize the palette payload for that workflow
4. only then translate the workflow into MCP or plugin API operations

Do not start from raw API calls. Start from the workflow structure.

## Available sub-skills

- `references/extract-source-colors.md` — extract fill colors from the current Framer selection to seed a palette
- `references/extract-styles-colors.md` — extract colors from Framer local color styles to seed a palette
- `references/generate-styles.md` — generate and update Framer local color styles
- `references/generate-preview.md` — draw the palette as a swatch board on the Framer canvas (canvas rendering only, not style export)

## Routing

Choose the sub-skill by user intent:

- “extract colors from selection”, “pick colors from selection”, “colors from Framer” → `references/extract-source-colors.md`
- “extract colors from styles”, “color styles”, “style library”, “seed from styles” → `references/extract-styles-colors.md`
- “styles”, “color styles”, “sync Framer colors” → `references/generate-styles.md`
- “full Framer handoff”, “styles + preview” → styles first (`references/generate-styles.md`), then preview (`references/generate-preview.md`)
- “preview”, “swatch board”, “canvas rendering”, “visual board” → `references/generate-preview.md`
- “semantic tokens”, “color system styles”, “system color styles”, `SystemData` present in context → `references/generate-styles.md` — **new semantic style set from `SystemData`**

When routing a `SystemData`-based workflow to `references/generate-styles.md`, pass `SystemData` opaquely. The sub-skill maps it as follows:
- **First**: ensure the palette's primitive color styles exist — create them if missing (mandatory prerequisite)
- Create one color style per token, named by the system name + token path (`/systemName/tokenPath`)
- The `light` value is resolved from the first theme ref; `dark` from the second (falls back to `light` if absent)
- Excluded tokens (`isExcluded: true`) and unbound first-theme refs (`shadeId: null`) are skipped

Note: Framer color styles support only `light` and `dark` values — not arbitrary theme modes. Systems with more than 2 themes will use only the first two; the user will be warned.
## Platform API references

An agent should think in terms of the Framer Plugin API surface, not only the plugin wrapper:

- **Color styles API**
  - get color styles
  - create color style
  - set style attributes
  - remove color style
- **Canvas / node API**
  - frames and child nodes
  - set parent, set attributes, selection
  - create/update visual preview documents
- **Permissions API**
  - permission checks before create, update, or remove operations

## MCP usage strategy

Use MCP or direct API calls as the execution layer, not as the skill structure.

- The root skill chooses the workflow.
- The reference file defines the expected inputs, transformations, and outputs.
- MCP/API calls execute the chosen workflow.

## Agent rule

The plugin bridge files are reference implementations. If the plugin action is unavailable, the agent should reproduce the same behavior directly through Framer API requests.

---

## Recommended subagent

Delegate this skill to **`palette-transitioner`**.

The `palette-transitioner` agent normalizes `PaletteData` into the correct row model for Framer (`styleRows`, `previewRows`), then routes execution through the appropriate Framer sub-skill.
