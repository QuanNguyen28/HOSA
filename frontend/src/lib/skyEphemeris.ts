import { Vector3 } from "three";
import type { LunarCoordinate } from "../types";

export type SkyTable = {
  start_utc: string;
  end_utc: string;
  step_seconds: number;
  vectors_km: number[][];
};

/** Same MOON_ME observer subtraction and ENU rotation as SharedEphemeris.topocentric. */
export function sampleSky(table: SkyTable, time: number, coordinate: LunarCoordinate, altitudeM: number) {
  const start = Date.parse(table.start_utc), end = Date.parse(table.end_utc);
  if (!(time >= start && time < end) || table.step_seconds !== 3600) return undefined;
  const fraction = (time-start)/(table.step_seconds*1000);
  const i = Math.floor(fraction), f = fraction-i;
  const a = table.vectors_km[i], b = table.vectors_km[i+1];
  if (!a || !b || a.length !== 6 || b.length !== 6 || !a.every(Number.isFinite) || !b.every(Number.isFinite)) return undefined;
  const vectors = a.map((v, j) => v+(b[j]-v)*f);
  const lat = coordinate.latitude*Math.PI/180, lon = coordinate.longitude*Math.PI/180;
  const up = new Vector3(Math.cos(lat)*Math.cos(lon), Math.cos(lat)*Math.sin(lon), Math.sin(lat));
  const east = new Vector3(-Math.sin(lon), Math.cos(lon), 0);
  const north = new Vector3().crossVectors(up, east);
  const observer = up.clone().multiplyScalar((1737400+altitudeM)/1000);
  const angle = (offset: number) => {
    const delta = new Vector3(vectors[offset], vectors[offset+1], vectors[offset+2]).sub(observer);
    const e = delta.dot(east), n = delta.dot(north), u = delta.dot(up);
    return { azimuthDeg: ((Math.atan2(e, n)*180/Math.PI)%360+360)%360,
      elevationDeg: Math.atan2(u, Math.hypot(e,n))*180/Math.PI };
  };
  // Three.js uses X/Z for the equatorial plane, Y north, and negative Z east.
  return { sun: angle(0), earth: angle(3),
    worldSun: new Vector3(vectors[0], vectors[2], -vectors[1]).normalize() };
}
