![GitHub last commit](https://img.shields.io/github/last-commit/a-ng-d/claude-ui-color-palette?color=informational) ![GitHub](https://img.shields.io/github/license/a-ng-d/claude-ui-color-palette?color=informational)

# UI Color Palette on Claude Code

A [Claude Code](https://code.claude.com/) plugin that brings color palette design, contrast auditing, code generation, and design tool synchronization directly into your AI-assisted workflow.

## Features

### Core skills

| Skill                        | Description                                                                                               |
| ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| `generate-source-colors`     | Generate source colors from an image (k-means), a text prompt (AI), or a base color (harmony)             |
| `scale-palette`              | Build a full palette with `get_palette` and export as code/tokens (CSS, Tailwind, SwiftUI, DTCG, …)      |
| `build-color-system`         | Define a semantic token taxonomy and bind it to palette primitives via `get_color_system`                 |
| `manage-palettes`            | Browse, publish, share, update, and delete palettes on the platform                                       |
| `audit-palette`              | Audit color pairs for WCAG 2.1 and APCA compliance with a global contrast score                           |

### Community skills

| Skill               | Description                                                         | Source                                                                                    |
| ------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `gh-cli`            | GitHub CLI (`gh`) comprehensive reference for all GitHub operations | [github/awesome-copilot](https://github.com/github/awesome-copilot)                       |
| `gitlab-cli-skills` | GitLab CLI (`glab`) command reference and workflows                 | [vince-winkintel/gitlab-cli-skills](https://github.com/vince-winkintel/gitlab-cli-skills) |

## MCP Servers

The plugin connects to the following MCP servers:

| Server               | Transport | URL                                        | Notes                         |
| -------------------- | --------- | ------------------------------------------ | ----------------------------- |
| **UI Color Palette** | HTTP      | `https://mcp.ui-color-palette.com/mcp` | Core palette engine           |
| **Figma**            | HTTP      | `https://mcp.figma.com/mcp`                | Remote Figma API              |
| **Figma Desktop**    | HTTP      | `http://127.0.0.1:3845/mcp`                | Local Figma app               |
| **Penpot**           | HTTP      | `${penpot_url}/mcp/stream?userToken=…`             | URL via `penpot_url` · token via `penpot_token` |
| **Sketch**           | HTTP      | `http://localhost:31126/mcp`               | Requires activation in Sketch |
| **Framer**           | HTTP      | User-specific URL                          | Requires Framer MCP plugin    |
| **GitHub**           | HTTP      | `https://api.githubcopilot.com/mcp/`       | Issues, PRs, repos            |
| **GitLab**           | HTTP      | `https://<instance>/api/v4/mcp`            | User-specific instance URL    |

## Agent

The plugin uses **uicper** as the default agent.

It acts as the top-level orchestrator for multi-step workflows such as:

- generate → audit → export
- generate → transition → sync to design tools
- retrieve/publish → audit → export

The orchestrator delegates specialized work to focused sub-agents:

- `palette-color-systemer` — guided semantic color system design: taxonomy pattern suggestion, intelligent binding proposals, iterative refinement, and `get_color_system` submission
- `palette-auditor` — WCAG/APCA audits, risk detection, remediation guidance
- `palette-codegen` — normalized projection and code/token generation
- `palette-publisher` — published palette retrieval, publication, update, visibility, deletion
- `palette-transitioner` — transition from `PaletteData` to variables, tokens, styles, swatches, and preview/document artifacts

The default agent is configured in `settings.json`:

```json
{
	"agent": "uicper"
}
```

## Installation

### From the Yelbolt marketplace

**Step 1 — Add the marketplace** (once per machine):

```bash
/plugin marketplace add yelbolt/claude-marketplace
```

**Step 2 — Install the plugin:**

```bash
/plugin install ui-color-palette@yelbolt
```

### Update

```bash
/plugin marketplace update yelbolt
```

### Alternative — direct GitHub install

```bash
/plugin install github:a-ng-d/claude-ui-color-palette
```

### From a local directory (development)

```bash
claude --plugin-dir ./claude-ui-color-palette
```

### User configuration

On first enable, the plugin prompts for optional config:

| Key | Sensitive | Description |
|---|---|---|
| `penpot_url` | No | Your Penpot instance base URL — Penpot Cloud: `https://design.penpot.app`, self-hosted: your own domain |
| `penpot_token` | Yes (keychain) | Your Penpot user token — find it in Penpot → Account → Integrations → MCP Server |
| `framer_mcp_url` | No | Your Framer MCP URL from the [Framer marketplace](https://www.framer.com/marketplace/plugins/mcp/) |
| `gitlab_url` | No | Your GitLab instance URL (e.g. `https://gitlab.company.com`) — leave empty if not using GitLab |

Sensitive values are stored in the system keychain and never written to `settings.json`. You can update them at any time with `/plugin config`.

## Usage

```bash
# Generate source colors from an image
/ui-color-palette:generate-source-colors https://example.com/photo.jpg 8

# Generate source colors from a mood description
/ui-color-palette:generate-source-colors a warm sunset over the ocean

# Generate source colors from a base color (harmony)
/ui-color-palette:generate-source-colors #3B82F6 triadic

# Build a palette and export to Tailwind v4
/ui-color-palette:scale-palette tailwind-v4

# Build a palette and export to CSS with OKLCH
/ui-color-palette:scale-palette css oklch

# Audit contrast of a color set
/ui-color-palette:audit-palette #1E293B #F8FAFC #3B82F6 #FFFFFF

# Browse community palettes
/ui-color-palette:manage-palettes sunset warm
```

## Prerequisites

| Server        | Requirement                                                                         |
| ------------- | ----------------------------------------------------------------------------------- |
| Penpot        | Provide your user token via `/plugin config` (Penpot → Account → Integrations → MCP Server) |
| Sketch        | Enable MCP in Sketch preferences                                                    |
| Framer        | Install the [MCP plugin](https://www.framer.com/marketplace/plugins/mcp/) in Framer |
| Figma Desktop | Run Figma desktop with MCP enabled                                                  |

## License

MIT
