import { describe, expect, it } from "vitest";
import { adjacentTrackPoint, bearingInView, compactTrack, horizonAt, wrappedTrackEdges, type HorizonProfile } from "./horizonView";

const profile: HorizonProfile = {height_m: 20, azimuth_step_deg: 90, coverage_complete: true,
  points: [0,90,180,270].map((az,i)=>({azimuth_deg: az, horizon_deg: i, coverage_complete: true, blocker_distance_m: 4000}))};
describe("Horizon panorama geometry", () => {
  it("interpolates cyclic bearings without filling incomplete terrain", () => {
    expect(horizonAt(profile,315)?.elevation).toBe(1.5);
    expect(horizonAt(profile,-45)?.elevation).toBe(1.5);
    const missing = {...profile, points: profile.points.map((p,i)=>i===0?{...p,coverage_complete:false,horizon_deg:null}:p)};
    expect(horizonAt(missing,315)).toBeUndefined();
    expect(horizonAt(missing,270)?.elevation).toBe(3);
  });
  it("keeps north-crossing Follow views continuous but breaks the trajectory seam", () => {
    expect(bearingInView(359,0)).toBe(-1);
    expect(bearingInView(1,359)).toBe(361);
    expect(adjacentTrackPoint(359,1)).toBe(false);
    expect(adjacentTrackPoint(15,16)).toBe(true);
    expect(adjacentTrackPoint(NaN,16)).toBe(false);
    expect(wrappedTrackEdges(359,1)).toEqual([[359,361],[-1,1]]);
    expect(wrappedTrackEdges(1,359)).toEqual([[1,-1],[361,359]]);
    expect(wrappedTrackEdges(15,16)).toEqual([]);
  });
  it("retains every supplied path sample in compact typed arrays", () => {
    const rows = Array.from({length:2881},(_,i)=>[i/10,-2+i/1000,.26]);
    const chunk = compactTrack({start_utc:"2000-01-01T00:00:00Z",end_utc:"2000-04-30T00:00:00Z",
      chunk_index:0,chunk_count:308,sampling_seconds:3600,sample_count:2881,bodies:{sun:rows,earth:rows}});
    expect(chunk.bodies.sun).toBeInstanceOf(Float32Array);
    expect(chunk.bodies.sun.length).toBe(2881*3);
    expect(chunk.bodies.sun.at(-2)).toBeCloseTo(.88,5);
    expect(chunk.chunk_count).toBe(308);
  });
});
