import { describe, expect, it } from "vitest";
import { HEIGHTS, HIDDEN_DEFAULT_SITE_IDS, SITES } from "./model";
import { DEFAULT_MISSION, missionIssue, missionRequest } from "../mvp/contracts";

describe("default locations and viewer presets", () => {
  it("offers all 27 named NASA regions without archived targets", () => {
    expect(SITES).toHaveLength(27);
    expect(new Set(SITES.map((site) => `${site.lat},${site.lon}`)).size).toBe(26);
    expect(SITES.some((site) => HIDDEN_DEFAULT_SITE_IDS.has(site.id))).toBe(false);
    expect(SITES.every((site) => site.group === "nasa" && !/^(Site\d|LM\d|NP[A-D]|DM\d|SL\d)/.test(site.name))).toBe(true);
    expect(SITES.find((site) => site.id === "connecting-ridge")).toMatchObject({lat: -89.4632, lon: -137.49});
    expect(SITES.find((site) => site.id === "shackleton-rim")).toMatchObject({lat: -89.7668, lon: -171.87});
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
