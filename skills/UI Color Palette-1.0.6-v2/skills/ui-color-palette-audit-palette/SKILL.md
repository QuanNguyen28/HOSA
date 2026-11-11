---
name: ui-color-palette-audit-palette
description: Audit color pairs for contrast compliance against WCAG 2.1 and APCA standards. Use when the user wants to check accessibility, validate color pairings, or compute a global contrast score for a palette.
argument-hint: <hex-colors...>
---

# Audit Contrast

Use the **ui-color-palette** MCP tool `get_palette` to generate a palette with contrast data, then analyze the results for WCAG and APCA compliance.

## MCP tool reference

**Tool**: `get_palette`

**Input schema**: see `ui-color-palette-scale-palette` for full `base` and `themes` field definitions. Key requirement: every theme must have `textColorsTheme: { lightColor: "#FFFFFF", darkColor: "#000000" }` for `textContrast` to be populated.

**Always pass `compact: true`** — returns a flat array of shade rows instead of the full nested `PaletteData` tree. Each row already has `theme`, `color`, `shade`, `hex`, `contrast`, and `textContrast` at the top level. All other color space values are omitted server-side.

## Pre-computed contrast data

Each shade includes pre-computed scores. **Do NOT recalculate contrast — just read the values.**

**Do NOT read `shade.contrast`** (shade vs palette background) — this skill only uses `shade.textContrast` (light/dark text on shade).

### `shade.textContrast` — light & dark text on shade (requires `textColorsTheme` set in theme)

| Field | Path | Type | Description |
| ----- | ---- | ---- | ----------- |
| WCAG light ratio | `textContrast.wcag.light.ratio` | number | White text on shade |
| WCAG light score | `textContrast.wcag.light.score` | `"A"` \| `"AA"` \| `"AAA"` | WCAG level |
| WCAG dark ratio | `textContrast.wcag.dark.ratio` | number | Black text on shade |
| WCAG dark score | `textContrast.wcag.dark.score` | `"A"` \| `"AA"` \| `"AAA"` | WCAG level |
| APCA light Lc | `textContrast.apca.light.lc` | number | White text Lc |
| APCA light usage | `textContrast.apca.light.recommendedUsage` | string | Recommended usage |
| APCA dark Lc | `textContrast.apca.dark.lc` | number | Black text Lc |
| APCA dark usage | `textContrast.apca.dark.recommendedUsage` | string | Recommended usage |

## Audit dataset

With `compact: true`, the API already returns a flat array — one object per shade. No transformation needed before Step 3.

### Row schema

Each row in the flat array has these fields:

| Column | Source path | Description |
| ------ | ----------- | ----------- |
| `theme` | Theme label |
| `color` | Color family name |
| `shade` | Shade label |
| `hex` | Display color |
| `textContrast.wcag.light.ratio` | White text WCAG ratio |
| `textContrast.wcag.light.score` | White text WCAG level |
| `textContrast.wcag.dark.ratio` | Black text WCAG ratio |
| `textContrast.wcag.dark.score` | Black text WCAG level |
| `textContrast.apca.light.lc` | White text APCA Lc |
| `textContrast.apca.light.recommendedUsage` | White text recommendation |
| `textContrast.apca.dark.lc` | Black text APCA Lc |
| `textContrast.apca.dark.recommendedUsage` | Black text recommendation |
| `best_text` | derived — `LIGHT` or `DARK` |
| `wcag_pass` | derived — `true` if light or dark passes AA |
| `apca_pass` | derived — `true` if light or dark has `|Lc| >= 60` |
| `global_pass` | derived — `true` if `wcag_pass` and `apca_pass` |

### CSV-like representation

Prefer producing or reasoning from a compact CSV-like block instead of the original nested JSON:

```csv
theme,color,shade,hex,wcag_light_ratio,wcag_light_score,wcag_dark_ratio,wcag_dark_score,apca_light_lc,apca_light_usage,apca_dark_lc,apca_dark_usage,best_text,wcag_pass,apca_pass,global_pass
Light,primary,50,#F8FAFC,1.07,A,17.58,AAA,-4.2,AVOID,106.0,FLUENT_TEXT,DARK,true,true,true
Light,primary,100,#E2E8F0,1.32,A,13.16,AAA,-11.5,AVOID,95.2,FLUENT_TEXT,DARK,true,true,true
```

This flattened representation is the preferred input for audit reasoning, summary statistics, and visualization.

## Standards

- **WCAG 2.1**: Contrast ratios — AA requires 4.5:1 for normal text, 3:1 for large text; AAA requires 7:1 / 4.5:1
- **APCA**: Lightness contrast (Lc) values — minimum Lc 60 for body text, Lc 45 for large text, Lc 30 for non-text

## Workflow

### Step 0 — Check session state (free)

**Before calling any tool**, check whether a `PaletteData` slot is already populated in the conversation context (e.g. produced by `ui-color-palette-scale-palette` in the same session).

- If a compact flat array (from a previous `get_palette` call with `compact: true`) is present → **skip to Step 3**. No API call needed.
- If only `base` + `themes` are present (no palette data) → continue to Step 1.
- If nothing is present → ask the user for the source (palette config, hex colors, or palette ID).

### Step 1 — Scope the audit (before calling the API)

Determine the minimum configuration required. Do not pass more themes than necessary.

Ask (or infer from context):

> Which theme do you want to audit?
> - **Light** (recommended)
> - **Dark**
> - **Both**
> If you do not answer, I will audit **Light** only.

If the user has multiple color families and only cares about a subset, ask which ones — otherwise include all.

**Important**: Pass only the scoped themes in the `themes` array. Removing unused themes significantly reduces the `get_palette` response size.

### Step 2 — Call `get_palette` (targeted)

Call `get_palette` with:
- The full `base` configuration (unchanged)
- Only the **selected theme(s)** in `themes` (not the full list if more exist)
- Ensure every theme has `textColorsTheme` set (e.g. `{ lightColor: "#FFFFFF", darkColor: "#000000" }`) — required for `textContrast` to be populated
- **`compact: true`** — mandatory for this skill; returns a flat array and omits all raw color values

### Step 3 — Python extraction

The `compact: true` response is already a flat array — no traversal needed. Pass it directly to Python to produce the audit CSV.

```python
import json, sys

data = json.load(sys.stdin)  # flat array of shade rows

FIELDS = [
    "theme", "color", "shade", "hex",
    "wcag_light_ratio", "wcag_light_score",
    "wcag_dark_ratio",  "wcag_dark_score",
    "apca_light_lc",    "apca_light_usage",
    "apca_dark_lc",     "apca_dark_usage",
    "best_text", "wcag_pass", "apca_pass", "global_pass",
]
print(",".join(FIELDS))

for row in data:
    tc = row.get("textContrast", {})
    wl = tc.get("wcag", {}).get("light", {})
    wd = tc.get("wcag", {}).get("dark",  {})
    al = tc.get("apca", {}).get("light", {})
    ad = tc.get("apca", {}).get("dark",  {})

    wcag_pass = wl.get("score") in ("AA", "AAA") or wd.get("score") in ("AA", "AAA")
    apca_pass = abs(al.get("lc", 0)) >= 60 or abs(ad.get("lc", 0)) >= 60
    best_text = "DARK" if abs(ad.get("lc", 0)) > abs(al.get("lc", 0)) else "LIGHT"

    out = [
        row.get("theme", ""), row.get("color", ""), row.get("shade", ""), row.get("hex", ""),
        wl.get("ratio", ""), wl.get("score", ""),
        wd.get("ratio", ""), wd.get("score", ""),
        al.get("lc", ""),    al.get("recommendedUsage", ""),
        ad.get("lc", ""),    ad.get("recommendedUsage", ""),
        best_text, wcag_pass, apca_pass, wcag_pass and apca_pass,
    ]
    print(",".join(str(v) for v in out))
```

**Reason only from the CSV output** — the raw JSON array is no longer needed once the CSV is produced.

### Step 4 — Analyze and output

1. Build the **data visualization** from the flattened rows (see output format below).
2. Compute the **global contrast score** as a consolidated percentage:
   - **WCAG pass rate** = (shades where at least one of light/dark passes AA) / total shades × 100
   - **APCA pass rate** = (shades where at least one of light/dark has |Lc| ≥ 60) / total shades × 100
   - **Global score** = average of WCAG pass rate and APCA pass rate, displayed as `XX%`
3. Flag failing pairs and provide actionable recommendations.

## Arguments

`$ARGUMENTS` can be a list of hex colors to audit or a palette ID.

- `/ui-color-palette:audit-palette #1E293B #F8FAFC #3B82F6 #FFFFFF`
- `/ui-color-palette:audit-palette palette-id-abc123`

## Output format

The response should have 3 layers: compact dataset, visual audit table, and global score.

### 1. Compact audit dataset

Start with a short CSV-like block or markdown table containing only the flattened audit rows needed for interpretation.

```csv
theme,color,shade,hex,wcag_light_ratio,wcag_dark_ratio,apca_light_lc,apca_dark_lc,best_text,wcag_pass,apca_pass
Light,primary,50,#F8FAFC,1.07,17.58,-4.2,106.0,DARK,true,true
Light,primary,100,#E2E8F0,1.32,13.16,-11.5,95.2,DARK,true,true
```

### 2. Visual audit table

Then present results per color as a visual table, one row per shade:

### Per-color table

**Color: `{colorName}`** `{sourceHex}`

| Shade | Swatch | Hex | Light WCAG | Dark WCAG | Light APCA | Dark APCA | Best text | Status |
| ----- | ------ | --- | ---------- | --------- | ---------- | --------- | --------- | ------ |
| 50 | `[#F8FAFC]` | #F8FAFC | 1.07 / A | 17.58 / AAA | -4.2 / AVOID | 106.0 / FLUENT_TEXT | Dark | Pass |
| 100 | `[#E2E8F0]` | #E2E8F0 | 1.32 / A | 13.16 / AAA | -11.5 / AVOID | 95.2 / FLUENT_TEXT | Dark | Pass |
| ... | | | | | | | | |

- **Best text**: recommend `Light` or `Dark` based on the highest WCAG score (prioritize AAA > AA > A), then highest APCA |Lc| as tiebreaker.
- **Status**: `Pass` if the shade has at least one readable text color for both WCAG AA and APCA body text; otherwise `Fail`.

### Global contrast score

```
╔══════════════════════════════════════════╗
║          GLOBAL CONTRAST SCORE           ║
║                                          ║
║              85%                         ║
║                                          ║
║  WCAG AA pass rate:  90% (27/30 shades)  ║
║  APCA body text:     80% (24/30 shades)  ║
║                                          ║
║  Failing shades: 3                       ║
╚══════════════════════════════════════════╝
```

### Failing shades summary

List every shade that fails both light and dark text for WCAG AA (ratio < 4.5) or APCA body text (|Lc| < 60):

| Color | Shade | Hex | Issue | Recommendation |
| ----- | ----- | --- | ----- | -------------- |
| primary | 400 | #60A5FA | Neither text passes AA | Darken to 500 or lighten to 300 |

End with the global score and recommendations.

## Tips

- **6 fields max per shade**: Follow the extraction budget strictly. Never read `shade.contrast`, `shade.rgb`, `shade.lch`, `shade.oklch`, `shade.lab`, `shade.oklab`, `shade.hsl`, `shade.hsluv`, `shade.hsv`, `shade.cmyk`, `shade.gl` — they are not needed and inflate context size.
- **Discard raw data immediately**: As soon as a shade's CSV row is produced, release the raw shade object. Reason exclusively from the flattened rows.
- **Scope before calling**: Pass only the required theme(s) in the `themes` array. Each extra theme multiplies the response size.
- **Re-use session state**: If `PaletteData` is already in context from a prior step, skip the API call entirely (Step 0).
- **`textColorsTheme` is required**: Ensure every theme has `textColorsTheme` set (e.g. `{ lightColor: "#FFFFFF", darkColor: "#000000" }`) — otherwise `textContrast` will be absent and the audit cannot proceed.
- **Hex to rgb conversion** (for `ColorConfiguration.rgb`): divide each 0–255 channel by 255. E.g. `#3B82F6` → `{ r: 0.23, g: 0.51, b: 0.96 }`.

---

## Recommended subagent

Delegate this skill to **`palette-auditor`**.

The `palette-auditor` agent is optimized for WCAG/APCA contrast audits, global contrast scoring, risky pair detection, and remediation proposals. It knows the audit dataset schema defined in this skill and works from the flattened row representation rather than traversing full `PaletteData`.
