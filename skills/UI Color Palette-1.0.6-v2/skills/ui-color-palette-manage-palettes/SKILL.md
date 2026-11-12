---
name: ui-color-palette-manage-palettes
description: Browse, publish, share, update, and delete palettes on the UI Color Palette platform. Use when the user wants to manage their published palettes or explore community palettes.
argument-hint: <action|search-query|palette-id>
---

# Manage Palettes

Use the **ui-color-palette** MCP tools for palette lifecycle management.

## Authentication

Tools marked **Auth: Yes** require a valid OAuth 2.1 Bearer token. The MCP client handles authentication automatically via the discovery endpoint (`/.well-known/oauth-authorization-server`) — no manual token management is needed.

If an authenticated call fails with a 401, instruct the user to sign in through their MCP client before retrying.

---

## Browse palettes

### `list_published_palettes` (Auth: No)

Browse public community palettes.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `page` | number | No | Page number (default: 1) |
| `limit` | number | No | Results per page, max 50 (default: 20) |
| `search` | string | No | Filter palettes by name |

### `get_published_palette` (Auth: No)

Fetch a specific palette by ID. Parameters: `paletteId` (string, required).

---

## Manage your palettes

### `list_my_published_palettes` (Auth: Yes)

List the authenticated user's own palettes.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `page` | number | No | Page number (default: 1) |
| `limit` | number | No | Results per page, max 50 (default: 20) |
| `search` | string | No | Filter palettes by name |

### `publish_palette` (Auth: Yes)

Publish a new palette.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `name` | string | Yes | Palette name |
| `description` | string | No | Palette description |
| `preset` | object | Yes | `PresetConfiguration` object |
| `shift` | object | Yes | `ShiftConfiguration` object (hue/saturation/lightness adjustments) |
| `are_source_colors_locked` | boolean | Yes | Whether source colors are pinned |
| `colors` | array | Yes | Array of color definition objects |
| `themes` | array | Yes | Array of `ThemeConfiguration` objects |
| `color_space` | string | Yes | Color space (e.g. `"LCH"`, `"OKLCH"`, `"RGB"`) |
| `algorithm_version` | string | Yes | Algorithm version (e.g. `"v2"`) |
| `is_shared` | boolean | No | Whether publicly visible (default: false) |

### `update_published_palette` (Auth: Yes)

Update an existing palette. All fields except `accessToken` and `paletteId` are optional — only send fields to change.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `paletteId` | string | Yes | Unique palette identifier |
| `name` | string | No | Updated name |
| `description` | string | No | Updated description |
| `preset` | object | No | Updated preset configuration |
| `shift` | object | No | Updated shift configuration |
| `are_source_colors_locked` | boolean | No | Updated lock state |
| `colors` | array | No | Updated color definitions |
| `themes` | array | No | Updated theme configurations |
| `color_space` | string | No | Updated color space |
| `algorithm_version` | string | No | Updated algorithm version |
| `is_shared` | boolean | No | Updated sharing visibility |

---

## Share & visibility

### `share_published_palette` (Auth: Yes)

Make a palette publicly visible. Parameters: `paletteId` (string, required).

### `unshare_published_palette` (Auth: Yes)

Remove a palette from the community listing. Parameters: `paletteId` (string, required).

---

## Delete

### `unpublish_palette` (Auth: Yes)

Permanently delete a palette. Parameters: `paletteId` (string, required).

---

## Workflow

### Browse palettes

1. Call `list_published_palettes` with optional `search` and `page`/`limit`.
2. Generate an HTML card list (see **Visual display** below) — never show raw JSON.

### Load a palette for reuse

1. Call `get_published_palette` with the `paletteId`.
2. Generate an HTML detail card (see **Visual display** below).
3. **Session state**: store the result as the `PublishedPaletteConfig` slot. It contains `colors`, `preset`, `shift`, `themes`, `color_space`, and `algorithm_version` — all the parameters needed to call `get_palette`.
4. Confirm to the user:

   > Palette **"Name"** loaded. You can now scale it, export code, or push it to a design tool — I'll use this configuration automatically.

`ui-color-palette-scale-palette` will detect the `PublishedPaletteConfig` slot and skip its Step 0 questions, going straight to the palette build.

### Publish a palette

1. If no OAuth session is active, instruct the user to authenticate through their MCP client.
2. Collect palette data (name, colors, themes, preset, shift, etc.).
3. Call `publish_palette` with the full payload.
4. Confirm publication and provide the palette ID.
5. Optionally call `share_published_palette` to make it publicly visible.

### Update a palette

1. Authenticate if needed.
2. Call `update_published_palette` with `paletteId` and only the fields to change.

---

## Visual display

Never show raw JSON for any palette response.

The source colors in published palettes are the **seed colors** (not the full shade ramp). Display them as colored blocks using `colors[i].name` as the label and the hex value as the ANSI background.

### After `list_published_palettes` or `list_my_published_palettes`

Use ANSI 24-bit background color codes. One block per source color, one palette per group:

```
Ocean Breeze -- OKLCH - Material - 2 themes - [public]
  primary   \033[48;2;37;99;235m      \033[0m  #2563EB
  neutral   \033[48;2;107;114;128m   \033[0m  #6B7280
ID: abc123

Sunset Warm -- LCH - Tailwind - 1 theme - [private]
  ...
```

Format per line: `  {name}   \033[48;2;{R};{G};{B}m      \033[0m  {hex}` where R, G, B are the decimal components of the hex color.

### After `get_published_palette`

Use ANSI with full metadata. Render this **before** the session state confirmation message.

```
Ocean Breeze
A cool ocean-inspired palette.
OKLCH - Material - Light + Dark - v3 - [private]

  primary   \033[48;2;37;99;235m      \033[0m  #2563EB
  neutral   \033[48;2;107;114;128m   \033[0m  #6B7280
  success   \033[48;2;22;163;74m     \033[0m  #16A34A

ID: abc123
```

#### Plain text fallback

If ANSI cannot be rendered, show a compact list:
Ocean Breeze -- OKLCH - Material - Light + Dark - v3 - [private]
  primary   #2563EB
  neutral   #6B7280
  success   #16A34A
ID: abc123
```

---

## Arguments

`$ARGUMENTS` can be:

- A search query: `/ui-color-palette:manage-palettes sunset warm`
- An action: `/ui-color-palette:manage-palettes list mine`
- A palette ID: `/ui-color-palette:manage-palettes get abc123`

## Tips

- Palettes are private by default after publication — the user must explicitly `share_published_palette` to make them public.
- Use `list_my_published_palettes` to find palette IDs for update/delete operations.
- The `preset`, `shift`, `colors`, and `themes` fields match the structures used by `get_palette`.
- **`preset.id` must be one of the 19 supported values** — never invent or guess an id. For the full list with canonical `stops`, `min`, `max`, and `easing` per id, refer to `ui-color-palette-scale-palette` Step 0 question 4. Always use those canonical values when building the preset object.
- **`shift.chroma` default is `100`, not `0`** — 100 means no change. A value of 0 fully desaturates all colors. Use `{ "chroma": 100, "hue": 0 }` when no shift is intended.
- **Default theme `id` and `name`**: for a single (unthemed) palette, the theme must have `id: "00000000000"` and `name: "None"`. For multi-theme palettes, generate a random 11-character lowercase hex string for each `id` and use descriptive names (`"Light"`, `"Dark"`, etc.).

---

## Recommended subagent

Delegate this skill to **`palette-publisher`**.

The `palette-publisher` agent handles all palette lifecycle operations: browse, retrieve, publish, update, share, unshare, and delete. It resolves authentication before any authenticated call and applies minimal update payloads.
