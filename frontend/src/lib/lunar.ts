import { Vector3 } from "three";

import type { LunarCoordinate } from "../types";

export const MOON_RADIUS_KM = 1737.4;
export const MOON_SCENE_RADIUS = 2;
export const SURFACE_CLICK_MAX_DELTA_PX = 4;

const DEG = Math.PI / 180;

export function coordinateToVector(
  coordinate: LunarCoordinate,
  radius = MOON_SCENE_RADIUS,
): Vector3 {
  const latitude = coordinate.latitude * DEG;
  const longitude = coordinate.longitude * DEG;
  const horizontal = Math.cos(latitude);

  return new Vector3(
    radius * horizontal * Math.cos(longitude),
    radius * Math.sin(latitude),
    -radius * horizontal * Math.sin(longitude),
  );
}

export function vectorToCoordinate(point: Vector3): LunarCoordinate {
  const normalized = point.clone().normalize();
  return {
    latitude: Math.asin(normalized.y) / DEG,
    longitude: Math.atan2(-normalized.z, normalized.x) / DEG,
  };
}

/**
 * Convert a raycast hit on the lunar globe to the application's lunar frame.
 *
 * React Three Fiber exposes `ThreeEvent.point` in world space. The Moon mesh is
 * rotated only to align its equirectangular textures, so applying
 * `mesh.worldToLocal()` before this conversion would rotate the hit by another
 * 180 degrees and place the selection on the opposite side of the globe.
 */
export function surfaceHitToCoordinate(worldPoint: Vector3): LunarCoordinate {
  return vectorToCoordinate(worldPoint);
}

export function isSurfaceSelectionGesture(pointerDeltaPx: number): boolean {
  return (
    Number.isFinite(pointerDeltaPx) &&
    pointerDeltaPx <= SURFACE_CLICK_MAX_DELTA_PX
  );
}

export function formatCoordinate(value: number, axis: "lat" | "lon"): string {
  const direction =
    axis === "lat" ? (value < 0 ? "S" : "N") : value < 0 ? "W" : "E";
  return `${Math.abs(value).toFixed(4)}° ${direction}`;
}

export function approximateSunVector(date: Date): Vector3 {
  const synodicMonthDays = 29.530588;
  const referenceNewMoon = Date.UTC(2026, 10, 9, 7, 2, 0);
  const elapsedDays = (date.getTime() - referenceNewMoon) / 86_400_000;
  const phase = ((elapsedDays / synodicMonthDays) % 1 + 1) % 1;
  const angle = phase * Math.PI * 2;
  const declination = 1.54 * DEG * Math.sin(angle);

  return new Vector3(
    Math.cos(declination) * Math.cos(angle),
    Math.sin(declination),
    -Math.cos(declination) * Math.sin(angle),
  ).normalize();
}

export function formatUtc(date: Date): string {
  return date.toISOString().replace(".000Z", "Z").replace("T", "  ");
}
