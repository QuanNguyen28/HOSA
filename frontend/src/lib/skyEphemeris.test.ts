import { describe, expect, it } from "vitest";
import { sampleSky } from "./skyEphemeris";
import reference from "./skyEphemeris.fixture.json";

describe("continuous SPICE sky directions", () => {
  it.each(reference.cases)("matches backend ENU at $at_utc, including month boundaries", (row) => {
    const sky = sampleSky(row.table, Date.parse(row.at_utc), row.coordinate, row.altitude_m)!;
    for (const body of ["sun", "earth"] as const) {
      expect(sky[body].azimuthDeg).toBeCloseTo(row.expected[body].azimuthDeg, 10);
      expect(sky[body].elevationDeg).toBeCloseTo(row.expected[body].elevationDeg, 10);
    }
    expect(sky.worldSun.length()).toBeCloseTo(1, 12);
  });
  it("never reuses a table outside its time coverage", () => {
    const row = reference.cases[0];
    expect(sampleSky(row.table, Date.parse(row.table.start_utc)-1, row.coordinate, row.altitude_m)).toBeUndefined();
    expect(sampleSky(row.table, Date.parse(row.table.end_utc), row.coordinate, row.altitude_m)).toBeUndefined();
  });
  it("interpolates vectors through north instead of rotating across the azimuth wrap", () => {
    const start = Date.parse("2026-01-01T00:00:00Z");
    const table = { start_utc: new Date(start).toISOString(), end_utc: new Date(start+3600000).toISOString(), step_seconds: 3600,
      vectors_km: [[1737.4,-1,100,384400,0,0],[1737.4,1,100,384400,0,0]] };
    const sky = sampleSky(table, start+1800000, { latitude: 0, longitude: 0 }, 0)!;
    expect(sky.sun.azimuthDeg).toBeCloseTo(0, 12);
    expect(sky.sun.elevationDeg).toBeCloseTo(0, 12);
  });
});
