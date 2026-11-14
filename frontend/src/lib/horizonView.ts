export type HorizonPoint = { azimuth_deg: number; horizon_deg: number | null; coverage_complete: boolean; blocker_distance_m: number | null };
export type HorizonProfile = { height_m: number; azimuth_step_deg: number; coverage_complete: boolean; points: HorizonPoint[] };
export type HorizonData = { source_sha256: string; coordinate: { dem_z_m: number }; profiles: HorizonProfile[] };
export type TrackChunk = { start_utc: string; end_utc: string; sampling_seconds: number; sample_count: number; chunk_index: number; chunk_count: number; bodies: Record<"sun" | "earth", number[][]> };
export type CompactTrack = Omit<TrackChunk, "bodies"> & { bodies: Record<"sun" | "earth", Float32Array> };
export const bearing = (value: number) => (value % 360 + 360) % 360;
export const bearingInView = (azimuth: number, centre: number) => centre + bearing(azimuth - centre + 180) - 180;

export type HorizonVisibility = 'visible' | 'hidden' | 'unknown';

/** Marker states prefer backend evidence; unassessed paths show centre geometry only. */
export function horizonVisibility(elevation: number, skyline?: { elevation: number }, state?: 'V' | 'B' | '?'): HorizonVisibility {
  if (state === 'V') return 'visible';
  if (state === 'B') return 'hidden';
  if (state === '?' || !Number.isFinite(elevation) || !skyline || !Number.isFinite(skyline.elevation)) return 'unknown';
  return elevation <= skyline.elevation ? 'hidden' : 'visible';
}

export function horizonAt(profile: HorizonProfile | undefined, azimuth: number) {
  if (!profile?.points.length) return undefined;
  const position = bearing(azimuth) / profile.azimuth_step_deg;
  const i = Math.floor(position) % profile.points.length, f = position - Math.floor(position);
  const a = profile.points[i], b = profile.points[(i+1) % profile.points.length];
  if (!a.coverage_complete || a.horizon_deg == null || (f > 1e-8 && (!b.coverage_complete || b.horizon_deg == null))) return undefined;
  return { elevation: a.horizon_deg * (1-f) + (b.horizon_deg ?? a.horizon_deg) * f, distance: a.blocker_distance_m };
}

export type HorizonSegment = { from: [number, number]; to: [number, number]; state: HorizonVisibility };

/** Split at skyline crossings and north, so a short hidden run is not erased. */
export function horizonTrackSegments(points: ArrayLike<number>, profile?: HorizonProfile): HorizonSegment[] {
  const segments: HorizonSegment[] = [];
  const add = (from: [number, number], to: [number, number], state: HorizonVisibility) => {
    if (from[0] === to[0] && from[1] === to[1]) return;
    if (to[0] < 0 || to[0] > 360) {
      const edge = to[0] < 0 ? 0 : 360, shift = edge === 0 ? 360 : -360;
      const elevation = from[1] + (to[1]-from[1]) * (edge-from[0])/(to[0]-from[0]);
      if(from[0]!==edge || from[1]!==elevation) segments.push({ from, to: [edge,elevation], state });
      if(to[0]!==edge || to[1]!==elevation) segments.push({ from: [edge+shift,elevation], to: [to[0]+shift,to[1]], state });
    } else segments.push({ from, to, state });
  };
  for (let i=3; i<points.length; i+=3) {
    const a: [number,number] = [bearing(points[i-3]),points[i-2]];
    const delta = bearing(points[i]-a[0]+180)-180;
    const b: [number,number] = [a[0]+delta,points[i+1]];
    if (![...a,...b].every(Number.isFinite)) continue;
    const ha = horizonAt(profile,a[0]), hb = horizonAt(profile,b[0]);
    if (!ha || !hb) { add(a,b,'unknown'); continue; }
    const ca=a[1]-ha.elevation, cb=b[1]-hb.elevation;
    const sa=horizonVisibility(a[1],ha), sb=horizonVisibility(b[1],hb);
    if(sa===sb) {add(a,b,sa);continue;}
    const f=ca/(ca-cb), crossing: [number,number] = [a[0]+delta*f,a[1]+(b[1]-a[1])*f];
    add(a,crossing,sa);
    // Normalize the second part if the first one crossed north already.
    const shift=crossing[0]<0?360:crossing[0]>360?-360:0;
    add([crossing[0]+shift,crossing[1]],[b[0]+shift,b[1]],sb);
  }
  return segments;
}

export function compactTrack(chunk: TrackChunk): CompactTrack {
  return { ...chunk, bodies: { sun: Float32Array.from(chunk.bodies.sun.flat()), earth: Float32Array.from(chunk.bodies.earth.flat()) } };
}

/** Break at the 0/360 seam; never draw a false line across the panorama. */
export function adjacentTrackPoint(previous: number, current: number) {
  return Number.isFinite(previous) && Number.isFinite(current) && Math.abs(current - previous) < 180;
}

export function wrappedTrackEdges(previous: number, current: number) {
  if (!Number.isFinite(previous) || !Number.isFinite(current) || Math.abs(current-previous) < 180) return [];
  const shift = previous > current ? 360 : -360;
  return [[previous, current+shift], [previous-shift, current]];
}
