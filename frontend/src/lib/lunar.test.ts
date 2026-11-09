import { describe, expect, it } from "vitest";

import {
  coordinateToVector,
  isSurfaceSelectionGesture,
  surfaceHitToCoordinate,
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

  it("does not apply the Moon texture rotation to the raycast hit", () => {
    const coordinate = { latitude: -75.8473, longitude: -132.3622 };
    const hit = coordinateToVector(coordinate);
    const restored = surfaceHitToCoordinate(hit);

    expect(restored.longitude).toBeCloseTo(-132.3622, 8);
    expect(Math.abs(restored.longitude - 47.6378)).toBeGreaterThan(179.9);
  });

  it("separates a surface click from a camera-drag gesture", () => {
    expect(isSurfaceSelectionGesture(0)).toBe(true);
    expect(isSurfaceSelectionGesture(4)).toBe(true);
    expect(isSurfaceSelectionGesture(4.01)).toBe(false);
    expect(isSurfaceSelectionGesture(730)).toBe(false);
  });
});
