import { describe, expect, it } from "vitest";
import { HEIGHTS, HIDDEN_DEFAULT_SITE_IDS, SITES } from "./model";
import { DEFAULT_MISSION, missionIssue, missionRequest } from "../mvp/contracts";

describe("default locations and viewer presets", () => {
  it("offers 19 real locations without archived P1 and example targets", () => {
    expect(SITES).toHaveLength(19);
    expect(SITES.some((site) => HIDDEN_DEFAULT_SITE_IDS.has(site.id))).toBe(false);
  });
  it.each(HEIGHTS)("supports %i m for both panel and antenna", (height) => {
    const mission = { ...DEFAULT_MISSION, panel: height, antenna: height };
    expect(missionIssue(mission)).toBeNull();
    const site = SITES[0];
    const request = missionRequest(mission, { id: site.id, name: site.name,
      latitude: site.lat, longitude: site.lon, elevationM: NaN, status: "provisional" });
    expect(request.panel_height_m).toBe(height);
    expect(request.antenna_height_m).toBe(height);
  });
});
