import { describe, expect, it } from "vitest";
import { loadHorizonProfile, type HorizonPreparation } from "./horizonPreload";
import type { HorizonData } from "./horizonView";
import type { MissionRequest } from "../mvp/contracts";

describe("automatic horizon loading", () => {
  it("waits for a background horizon without requesting Analyze", async () => {
    const profile = { source_sha256: "geometry" } as HorizonData;
    const states: HorizonPreparation[] = [{status: "preparing", stage: "terrain_horizon", retry_after_ms: 750},
      {status: "ready", profile}];
    const delays: number[] = [];
    const loaded = await loadHorizonProfile({} as MissionRequest, async () => states.shift()!, async ms => {delays.push(ms);});
    expect(loaded).toBe(profile);
    expect(delays).toEqual([750]);
  });
  it("backs off a full queue and preserves source errors", async () => {
    let calls = 0;
    const profile = {} as HorizonData;
    const delays: number[] = [];
    await expect(loadHorizonProfile({} as MissionRequest, async () => {
      if (calls++ === 0) throw new Error("HORIZON_PREPARATION_BUSY");
      return {status: "ready", profile};
    }, async ms => {delays.push(ms);})).resolves.toBe(profile);
    expect(delays).toEqual([1500]);
    await expect(loadHorizonProfile({} as MissionRequest,
      async () => {throw new Error("OUTSIDE_DEM_COVERAGE");}, async () => {})).rejects.toThrow("OUTSIDE_DEM_COVERAGE");
  });
});
