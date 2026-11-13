export type HorizonPoint = { azimuth_deg: number; horizon_deg: number | null; coverage_complete: boolean; blocker_distance_m: number | null };
export type HorizonProfile = { height_m: number; azimuth_step_deg: number; coverage_complete: boolean; points: HorizonPoint[] };
export type HorizonData = { source_sha256: string; coordinate: { dem_z_m: number }; profiles: HorizonProfile[] };
export type TrackChunk = { start_utc: string; end_utc: string; sampling_seconds: number; sample_count: number; chunk_index: number; chunk_count: number; bodies: Record<"sun" | "earth", number[][]> };
export type CompactTrack = Omit<TrackChunk, "bodies"> & { bodies: Record<"sun" | "earth", Float32Array> };
export const bearing = (value: number) => (value % 360 + 360) % 360;
export const bearingInView = (azimuth: number, centre: number) => centre + bearing(azimuth - centre + 180) - 180;

export function horizonAt(profile: HorizonProfile | undefined, azimuth: number) {
  if (!profile?.points.length) return undefined;
  const position = bearing(azimuth) / profile.azimuth_step_deg;
  const i = Math.floor(position) % profile.points.length, f = position - Math.floor(position);
  const a = profile.points[i], b = profile.points[(i+1) % profile.points.length];
  if (!a.coverage_complete || a.horizon_deg == null || (f > 1e-8 && (!b.coverage_complete || b.horizon_deg == null))) return undefined;
  return { elevation: a.horizon_deg * (1-f) + (b.horizon_deg ?? a.horizon_deg) * f, distance: a.blocker_distance_m };
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
