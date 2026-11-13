import { describe, expect, it } from "vitest";
import { PerspectiveCamera, Vector3 } from "three";
import { sceneContent, terrainCameraPose } from "./terrainCamera";
import { skyDirectionToTerrainAxes, type TerrainGeometryMetadata } from "./terrainGeometry";

describe("upright local terrain cameras", () => {
  it("never substitutes a zoomed Moon for pending Ground/Pole terrain", () => {
    for (const preset of ["surface", "south-pole"] as const) {
      expect(sceneContent(preset, false)).toBe("pending");
      expect(sceneContent(preset, true)).toBe("terrain");
    }
    expect(sceneContent("orbit", false)).toBe("moon");
    expect(sceneContent("orbit", true)).toBe("moon");
  });
  const axes = { column_azimuth_deg: 27, row_azimuth_deg: 117 } as TerrainGeometryMetadata;
  it.each(["surface", "south-pole"] as const)("removes inherited Moon roll in %s", (preset) => {
    const camera = new PerspectiveCamera();
    camera.up.set(0.8, -0.3, 0.5).normalize();
    const pose = terrainCameraPose(preset, axes);
    camera.up.set(...pose.up);
    camera.position.set(...pose.position);
    camera.lookAt(new Vector3(...pose.target));
    const screenUp = new Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
    expect(camera.up.toArray()).toEqual([0, 1, 0]);
    expect(screenUp.y).toBeGreaterThan(0);
    const north = skyDirectionToTerrainAxes(0, 0, axes);
    const forward = new Vector3(...pose.target).sub(camera.position);
    expect(forward.x * north.x + forward.z * north.z).toBeGreaterThan(0);
  });
  it("handles opposite terrain projections without reversing zenith", () => {
    for (const azimuth of [0, 90, 180, 270]) {
      const pose = terrainCameraPose("surface", { ...axes, column_azimuth_deg: azimuth, row_azimuth_deg: azimuth + 90 });
      expect(pose.up).toEqual([0, 1, 0]);
      expect(Math.hypot(pose.position[0], pose.position[2])).toBeCloseTo(0.38);
      expect(pose.position[1]).toBeGreaterThan(pose.target[1]);
    }
  });
});
