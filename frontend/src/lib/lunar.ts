import { Ray, Sphere, Vector3 } from "three";

import type { LunarCoordinate } from "../types";
import type { TerrainGeometryMetadata } from "./terrainGeometry";

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
 * React Three Fiber exposes `ThreeEvent.point` in world space. Interactive
 * lunar geometry remains in MOON_ME; raster alignment is performed in UV space
 * so raycasts and markers share this same frame.
 */
export function surfaceHitToCoordinate(worldPoint: Vector3): LunarCoordinate {
  return vectorToCoordinate(worldPoint);
}

/**
 * Resolve a pointer ray against the lunar reference sphere.
 *
 * Terrain overlays can contain overlapping LOD meshes, lines and transparent
 * pixels, so a bubbled R3F event's `point` is not guaranteed to belong to the
 * surface that visually sits under the pointer. The event ray is camera-derived
 * and remains authoritative. Intersecting that ray with the reference sphere
 * keeps custom-point selection screen-aligned while the backend supplies the
 * precise DEM elevation and suitability values for the resulting coordinate.
 */
export function surfaceRayToCoordinate(
  ray: Ray,
  radius = MOON_SCENE_RADIUS,
): LunarCoordinate | null {
  const hit = ray.intersectSphere(
    new Sphere(new Vector3(0, 0, 0), radius),
    new Vector3(),
  );
  return hit ? vectorToCoordinate(hit) : null;
}

/** Convert a world-space hit on a local DEM mesh back to lunar coordinates. */
export function terrainHitToCoordinate(
  worldPoint: Vector3,
  origin: LunarCoordinate,
  metadata: TerrainGeometryMetadata,
): LunarCoordinate {
  if (
    Number.isFinite(metadata.center_x_m) &&
    Number.isFinite(metadata.center_y_m) &&
    metadata.projection === "spherical south polar stereographic"
  ) {
    const projectedX = metadata.center_x_m! + worldPoint.x * 1_000;
    // DEM rows advance toward decreasing projected Y while local mesh Z grows.
    const projectedY = metadata.center_y_m! - worldPoint.z * 1_000;
    const rho = Math.hypot(projectedX, projectedY);
    const latitude = -Math.PI / 2
      + 2 * Math.atan(rho / (2 * metadata.lunar_reference_radius_m));
    const longitude = Math.atan2(projectedX, projectedY);
    return {
      latitude: latitude / DEG,
      longitude: longitude / DEG,
    };
  }

  // Backward-compatible tangent-frame inverse for older cached responses.
  const latitude = origin.latitude * DEG;
  const longitude = origin.longitude * DEG;
  const up = coordinateToVector(origin, 1).normalize();
  const east = new Vector3(-Math.sin(longitude), 0, -Math.cos(longitude));
  const north = new Vector3(
    -Math.sin(latitude) * Math.cos(longitude),
    Math.cos(latitude),
    Math.sin(latitude) * Math.sin(longitude),
  );
  const axisAt = (azimuthDeg: number) => east.clone()
    .multiplyScalar(Math.sin(azimuthDeg * DEG))
    .add(north.clone().multiplyScalar(Math.cos(azimuthDeg * DEG)))
    .normalize();
  const radiusKm = metadata.lunar_reference_radius_m / 1_000;
  return vectorToCoordinate(
    up
      .addScaledVector(axisAt(metadata.column_azimuth_deg), worldPoint.x / radiusKm)
      .addScaledVector(axisAt(metadata.row_azimuth_deg), worldPoint.z / radiusKm)
      .normalize(),
  );
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
