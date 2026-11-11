---
name: ui-color-palette-help
description: Display a quick-start guide and list all available commands. Use when the user wants to know what they can do, how to get started, or which command to use.
argument-hint:
- topic
---

# Help & Onboarding

Display this guide as a formatted response. No tools needed.

---

## What is UI Color Palette?

A complete color system workflow in Claude — from source colors to design tools and code export.

You can build a palette from scratch, audit its accessibility, push it to Figma/Penpot/Framer/Sketch, export it as CSS/Tailwind/DTCG, and manage published palettes — all in one conversation.

---

## The 4 phases

```
Source → Palette → Deploy → Manage
```

| Phase | What happens |
| ----- | ------------ |
| **1 · Source** | Pick or generate source colors (image, prompt, harmony, existing palette) |
| **2 · Palette** | Build a full shade scale, retrieve an existing palette, or audit contrast |
| **3 · Deploy** | Export as code or push to a design tool |
| **4 · Manage** | Publish, update, share, or delete a palette on the platform |

Just describe what you want and the orchestrator will guide you through each phase one step at a time.

---

## Commands

Invoke a specific skill directly with `/ui-color-palette:<command>`.

### Source

| Command | What it does |
| ------- | ------------ |
| `/ui-color-palette:generate-source-colors` | Extract colors from an image, a prompt, or a base color |

### Palette

| Command | What it does |
| ------- | ------------ |
| `/ui-color-palette:scale-palette` | Build a full shade palette from source colors |
| `/ui-color-palette:manage-palettes` | Browse, retrieve, or search published palettes |
| `/ui-color-palette:audit-palette` | Audit contrast (WCAG 2.1 + APCA) |

### Deploy — Code

| Command | What it does |
| ------- | ------------ |
| `/ui-color-palette:generate-code` | Export palette as CSS, SCSS, Tailwind v3/v4, DTCG, SwiftUI, Compose… |

### Deploy — Design tools

| Command | What it does |
| ------- | ------------ |
| `/ui-color-palette:figma` | Push variables or styles to Figma |
| `/ui-color-palette:penpot` | Push tokens or styles to Penpot |
| `/ui-color-palette:framer` | Push styles to Framer |
| `/ui-color-palette:sketch` | Push variables or styles to Sketch |

### Manage

| Command | What it does |
| ------- | ------------ |
| `/ui-color-palette:manage-palettes` | Publish, update, share, unshare, or delete a palette |

### Meta

| Command | What it does |
| ------- | ------------ |
| `/ui-color-palette:help` | Show this guide |

---

## Agents

For focused, high-complexity tasks, these sub-agents are available:

| Agent | When to use |
| ----- | ----------- |
| `palette-auditor` | Deep accessibility audit, WCAG/APCA scoring, remediation |
| `palette-codegen` | Multi-format or complex code/token export |
| `palette-transitioner` | Convert PaletteData to variables, tokens, styles, or swatches |
| `palette-publisher` | Palette lifecycle (publish, update, share, delete) |

---

## Quick starts

**I want to build a palette from scratch**
> Just say: *"Build a palette"* — the orchestrator will ask for colors, color space, scale, and themes.

**I have a brand color and want a Tailwind config**
> `/ui-color-palette:scale-palette` → then `/ui-color-palette:generate-code tailwind-v4`

**I want to check if my colors are accessible**
> `/ui-color-palette:audit-palette` with your hex values

**I want to push my palette to Figma**
> `/ui-color-palette:figma` — will ask whether you need variables or styles

**I already have a palette and want to export CSS**
> `/ui-color-palette:generate-code css` — no need to rebuild, the palette stays in context

---

## Tips

- The active `PaletteData` is kept in context for the whole session — no need to rebuild it between steps.
- You can chain phases: build → audit → export → push to Figma, all in one conversation.
- If you're unsure which command to use, just describe your goal in plain language.

## Arguments

`$ARGUMENTS` can be a topic to focus the help output:

- `/ui-color-palette:help deploy` — show only deploy commands
- `/ui-color-palette:help figma` — show Figma-specific guidance
- `/ui-color-palette:help code` — show code export formats
