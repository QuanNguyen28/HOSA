import { describe, expect, it } from "vitest";
import {
  DEFAULT_MISSION,
  EXAMPLES,
  boundsText,
  intervalAt,
  missionIssue,
  missionRequest,
  planningRequest,
  timelineBins,
  type Interval,
} from "./contracts";
import { errorText } from "./api";

describe("shared backend mission contracts", () => {
  it("weights solar disc display bins by duration and preserves missing evidence", () => {
    const start = Date.parse("2026-11-17T00:00:00Z");
    const row = (a: number, b: number, fraction: number | null): Interval => ({
      start_utc: new Date(start + a * 60000).toISOString(),
      end_utc: new Date(start + b * 60000).toISOString(),
      sun_state: fraction == null ? "?" : fraction > 0 ? "V" : "B", earth_state: "V", joint_state: "V",
      sun_visible_fraction: fraction,
    });
    const bin = timelineBins([row(0, 15, 0), row(15, 60, 1)], start, start + 3600000, 1)[0];
    expect(bin.sun_visible_fraction).toBe(0.75);
    const missing = timelineBins([row(0, 15, null), row(15, 60, 1)], start, start + 3600000, 1)[0];
    expect(missing.sun_visible_fraction).toBeNull();
    expect(missing.sun_state).toBe("?");
    expect(missing.sun_visible_fraction_lower).toBe(.75);
    expect(missing.sun_visible_fraction_upper).toBe(1);
  });
  it("preserves Earth and joint time fractions when rebinning prepared charts", () => {
    const start = Date.parse("2026-11-17T00:00:00Z");
    const row = (a: number, b: number, state: "V" | "B"): Interval => ({
      start_utc: new Date(start+a*60000).toISOString(), end_utc: new Date(start+b*60000).toISOString(),
      sun_state: "V", earth_state: state, joint_state: state,
    });
    const bin = timelineBins([row(0, 15, "B"), row(15, 60, "V")], start, start+3600000, 1)[0];
    expect(bin.aggregated).toBe(true);
    expect(bin.earth_state).toBe("?");
    expect(bin.earth_visible_fraction_lower).toBe(.75);
    expect(bin.earth_visible_fraction_upper).toBe(.75);
    expect(bin.joint_visible_fraction_lower).toBe(.75);
    expect(intervalAt([bin], start+1800000)).toBeUndefined();
  });
  it("uses identical mission requirements for direct analysis and comparison", () => {
    const direct = missionRequest(DEFAULT_MISSION, EXAMPLES[0]);
    const compare = planningRequest(DEFAULT_MISSION, EXAMPLES);
    expect(compare.arrival_utc).toBe(direct.start_utc);
    expect(compare.duration_hours).toBe(direct.duration_hours);
    expect(compare.hardware).toEqual({
      sun_panel: direct.panel_height_m,
      earth_antenna: direct.antenna_height_m,
    });
    expect(compare.contact_requirements).toEqual(direct.contact_requirements);
    expect(compare.resolve_indeterminate).toBe(true);
    expect(direct.resolve_indeterminate).toBe(true);
    expect(compare.min_sunlit_fraction).toBe(0.8);
    expect(compare.data_source).toBe("coordinate");
    expect(direct.illumination_model).toBe("solar_disc");
    expect(compare.illumination_model).toBe("solar_disc");
    expect(compare.targets[0]).toEqual({
      latitude_deg: direct.latitude_deg,
      longitude_e_deg: direct.longitude_e_deg,
    });
    expect(compare).not.toHaveProperty("min_earth_los_fraction");
  });
  it.each([
    { hours: -1 },
    { hours: 1.01 },
    { start: "2026-11-24T00:01" },
    { panel: 31 },
    { antenna: 0 },
    { deadline: 4321 },
    { windows: 1.5 },
    { hours: NaN },
    { start: "" },
  ])("rejects unsupported settings before submitting: %j", (change) =>
    expect(missionIssue({ ...DEFAULT_MISSION, ...change })).not.toBeNull(),
  );
  it("accepts the documented baseline", () =>
    expect(missionIssue(DEFAULT_MISSION)).toBeNull());
  it("accepts durations beyond a year without an application cap", () => {
    const mission = { ...DEFAULT_MISSION, hours: 17520, darkness: 10000 };
    expect(missionIssue(mission)).toBeNull();
    expect(missionRequest(mission, EXAMPLES[0]).duration_hours).toBe(17520);
  });
  it("uses the same target end date and derived duration in point and planning requests", () => {
    const mission = {
      ...DEFAULT_MISSION,
      timing: "end" as const,
      start: "2026-11-17T00:00",
      end: "2026-11-27T00:05",
      hours: 72,
    };
    expect(missionIssue(mission)).toBeNull();
    const point = missionRequest(mission, EXAMPLES[0]);
    const plan = planningRequest(mission, EXAMPLES);
    expect(point.duration_hours).toBe(240 + 1 / 12);
    expect(point.end_utc).toBe("2026-11-27T00:05:00.000Z");
    expect(plan.duration_hours).toBe(point.duration_hours);
    expect(plan.end_utc).toBe(point.end_utc);
  });
  it.each(["2026-11-23T00:00", "2026-11-27T00:01", ""])(
    "rejects invalid target end date %s",
    (end) => {
      expect(
        missionIssue({ ...DEFAULT_MISSION, timing: "end", end }),
      ).not.toBeNull();
    },
  );
  it("preserves offline mode", () =>
    expect(
      planningRequest({ ...DEFAULT_MISSION, offline: true }, EXAMPLES).offline,
    ).toBe(true));
  it("does not turn absent or uncertain numbers into zero", () => {
    expect(boundsText(undefined)).toBe("—");
    expect(boundsText([0, 72])).toBe("0–72");
    expect(boundsText([72, 72])).toBe("72");
    expect(boundsText([71.999999, 72])).toBe("72");
    expect(boundsText([53.63001, 53.63002])).toBe("53.63");
    expect(boundsText([53.63, 53.65])).toBe("53.63–53.65");
    expect(boundsText([50.01, 50.02], 1)).toBe("50");
  });
  it("uses half-open backend intervals", () => {
    const rows: Interval[] = [
      {
        start_utc: "2026-11-24T00:00:00Z",
        end_utc: "2026-11-24T00:05:00Z",
        sun_state: "?",
        earth_state: "B",
        joint_state: "B",
      },
    ];
    expect(intervalAt(rows, Date.parse(rows[0].start_utc))?.sun_state).toBe(
      "?",
    );
    expect(intervalAt(rows, Date.parse(rows[0].end_utc))).toBeUndefined();
  });
  it("renders structured domain errors and schema validation errors", () => {
    expect(errorText({ detail: { code: "HORIZONS_CACHE_MISS" } }, 503)).toBe(
      "HORIZONS_CACHE_MISS",
    );
    expect(
      errorText(
        { detail: [{ loc: ["body", "duration_hours"], msg: "Maximum 72" }] },
        422,
      ),
    ).toBe("duration_hours: Maximum 72");
  });
});
