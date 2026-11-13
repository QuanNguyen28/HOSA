import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ValidationInfo, BackendTimeline } from "../figma/backend";
import type { PointResult } from "./contracts";

describe("hard-first explanation", () => {
  it("shows the failed threshold and evidence dates without claiming validation ran", () => {
    const result = { decision: "FAIL", validation: { passed: false, status: "skipped_hard_failure" }, hard_failure: {
      constraint: "min_sunlit_fraction", limit: .8, observed_bounds: [0, 0], shortfall_hours_bounds: [57.6, 57.6],
      window: { start_utc: "2026-11-17T00:00:00Z", end_utc: "2026-11-20T00:00:00Z" },
      explanation: "Whole-window shortfall.", evidence_intervals: [{ target: "sun", start_utc: "2026-11-17T00:00:00Z", end_utc: "2026-11-18T00:00:00Z" }],
    } } as unknown as PointResult;
    const html = renderToStaticMarkup(<ValidationInfo result={result} onTime={() => {}} />);
    expect(html).toContain("Required 80.00%; upper bound 0.00%");
    expect(html).toContain("Validation and soft preferences skipped");
    expect(html).toContain("2026-11-17 00:00:00Z");
    expect(html).not.toContain("Validation incomplete or failed");
    result.hard_failure!.confirmed_sampling_minutes = [5, 1];
    const confirmed = renderToStaticMarkup(<ValidationInfo result={result} />);
    expect(confirmed).toContain("Hard failure confirmed on 5/1-minute grids");
    expect(confirmed).toContain("Full validation and soft preferences skipped");
  });
});

describe("prepared preview charts", () => {
  it("shows known averages in color and uncertain bounds as hatching", () => {
    const start = Date.parse("2026-11-17T00:00:00Z"), end = start+3600000;
    const result = { timeline: [{ start_utc: new Date(start).toISOString(), end_utc: new Date(end).toISOString(),
      aggregated: true, sun_state: "?", earth_state: "?", joint_state: "?",
      sun_visible_fraction_lower: .5, sun_visible_fraction_upper: .5,
      earth_visible_fraction_lower: .75, earth_visible_fraction_upper: .75,
      joint_visible_fraction_lower: .25, joint_visible_fraction_upper: .75,
    }], timeline_transport: { mode: "aggregated", exact_intervals_ready: false } } as unknown as PointResult;
    const html = renderToStaticMarkup(<BackendTimeline result={result} start={start} end={end} time={start} onTime={() => {}} />);
    expect(html).toContain("height:50%");
    expect(html).toContain("height:75%");
    expect(html).toContain("background:#06B6D4");
    expect(html).toContain("repeating-linear-gradient");
    expect(html).toContain("75.0% visible time in display bin");
    expect(html).toContain("Preview chart; exact instants available after Analyze");
  });
});
