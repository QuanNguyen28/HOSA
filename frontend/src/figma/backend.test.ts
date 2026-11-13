import { describe, expect, it } from "vitest";
import { jointBounds, matches, toTarget } from "./backend";
import { SITES } from "./model";
import type { Candidate, PointResult } from "../mvp/contracts";

describe("Figma shell backend adapters", () => {
  it("submits original catalog coordinates without relabeling them as P1", () => {
    const target = toTarget(SITES[0]);
    expect(target.id).toBe("connecting-ridge");
    expect(target.latitude).toBe(SITES[0].lat);
    expect(target.longitude).toBe(SITES[0].lon);
    expect(target.id).not.toBe("Site01_P1");
  });
  it("preserves unknown duration when summarizing the native joint timeline", () => {
    const result = {
      timeline: [
        {
          start_utc: "2026-11-24T00:00:00Z",
          end_utc: "2026-11-24T00:05:00Z",
          joint_state: "V",
        },
        {
          start_utc: "2026-11-24T00:05:00Z",
          end_utc: "2026-11-24T00:15:00Z",
          joint_state: "?",
        },
        {
          start_utc: "2026-11-24T00:15:00Z",
          end_utc: "2026-11-24T00:20:00Z",
          joint_state: "B",
        },
      ],
    } as PointResult;
    const [lo, hi] = jointBounds(result);
    expect(lo).toBeCloseTo(5 / 60);
    expect(hi).toBeCloseTo(15 / 60);
  });
  it("matches negative and positive east longitudes without mixing different points", () => {
    const site = { ...SITES[0], lon: -137.17 };
    const candidate = {
      coordinate: { latitude_deg: site.lat, longitude_e_deg: 222.83 },
    } as Candidate;
    expect(matches(site, candidate)).toBe(true);
    expect(matches({ ...site, lat: -87 }, candidate)).toBe(false);
    expect(matches(site, {} as Candidate)).toBe(false);
  });
  it("summarizes joint time from aggregated fraction bounds rather than mixed states", () => {
    const result = { timeline: [{ start_utc: "2026-11-24T00:00:00Z", end_utc: "2026-11-25T00:00:00Z",
      aggregated: true, joint_state: "?", joint_visible_fraction_lower: .5, joint_visible_fraction_upper: .75 }] } as PointResult;
    expect(jointBounds(result)).toEqual([12, 18]);
  });
});
