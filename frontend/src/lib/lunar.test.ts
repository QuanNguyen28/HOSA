import { describe, expect, it } from "vitest";
import {
  PerspectiveCamera,
  Raycaster,
  Vector2,
  Vector3,
} from "three";

import {
  coordinateToVector,
  isSurfaceSelectionGesture,
  surfaceHitToCoordinate,
  surfaceRayToCoordinate,
  terrainHitToCoordinate,
} from "./lunar";


describe("lunar globe coordinate transforms", () => {
  it.each([
    { latitude: 0, longitude: 0 },
    { latitude: -75.8473, longitude: -132.3622 },
    { latitude: -89.4389, longitude: -137.096 },
    { latitude: 42.25, longitude: 179.75 },
  ])("keeps a world-space surface hit at $latitude, $longitude", (coordinate) => {
    const hit = coordinateToVector(coordinate);
    const restored = surfaceHitToCoordinate(hit);

    expect(restored.latitude).toBeCloseTo(coordinate.latitude, 8);
    expect(restored.longitude).toBeCloseTo(coordinate.longitude, 8);
  });

  it("keeps raster alignment out of the geographic coordinate transform", () => {
    const coordinate = { latitude: -75.8473, longitude: -132.3622 };
    const hit = coordinateToVector(coordinate);
    const restored = surfaceHitToCoordinate(hit);

    expect(restored.longitude).toBeCloseTo(-132.3622, 8);
    expect(Math.abs(restored.longitude - 47.6378)).toBeGreaterThan(179.9);
  });

  it("keeps a ray-selected marker under the same screen-space pointer", () => {
    const camera = new PerspectiveCamera(36, 16 / 9, 0.1, 100);
    camera.position.set(0, 0.35, 6.4);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld(true);
    const pointer = new Vector2(-0.31, 0.22);
    const raycaster = new Raycaster();
    raycaster.setFromCamera(pointer, camera);

    const coordinate = surfaceRayToCoordinate(raycaster.ray);
    expect(coordinate).not.toBeNull();
    const projected = coordinateToVector(coordinate!).project(camera);

    expect(projected.x).toBeCloseTo(pointer.x, 8);
    expect(projected.y).toBeCloseTo(pointer.y, 8);
  });

  it("separates a surface click from a camera-drag gesture", () => {
    expect(isSurfaceSelectionGesture(0)).toBe(true);
    expect(isSurfaceSelectionGesture(4)).toBe(true);
    expect(isSurfaceSelectionGesture(4.01)).toBe(false);
    expect(isSurfaceSelectionGesture(730)).toBe(false);
  });

  it("maps a local DEM hit through the south-polar projection without mirroring", () => {
    const radiusM = 1_737_400;
    const project = (latitudeDeg: number, longitudeDeg: number) => {
      const latitude = latitudeDeg * Math.PI / 180;
      const longitude = longitudeDeg * Math.PI / 180;
      const rho = 2 * radiusM * Math.tan((latitude + Math.PI / 2) / 2);
      return [rho * Math.sin(longitude), rho * Math.cos(longitude)] as const;
    };
    const origin = { latitude: -89.4398, longitude: -137.17 };
    const target = { latitude: -88.72, longitude: -121.4 };
    const [centerX, centerY] = project(origin.latitude, origin.longitude);
    const [targetX, targetY] = project(target.latitude, target.longitude);
    const restored = terrainHitToCoordinate(
      new Vector3(
        (targetX - centerX) / 1_000,
        0,
        (centerY - targetY) / 1_000,
      ),
      origin,
      {
        horizontal_scale: 1,
        vertical_scale: 1,
        horizontal_unit: "metre",
        vertical_unit: "metre",
        lunar_reference_radius_m: radiusM,
        center_elevation_m: 0,
        center_x_m: centerX,
        center_y_m: centerY,
        column_azimuth_deg: 90,
        row_azimuth_deg: 180,
        projection: "spherical south polar stereographic",
        surface_model: "test",
      },
    );

    expect(restored.latitude).toBeCloseTo(target.latitude, 8);
    expect(restored.longitude).toBeCloseTo(target.longitude, 8);
  });
});
