import type { CameraPreset } from "../types";
import { skyDirectionToTerrainAxes, type TerrainGeometryMetadata } from "./terrainGeometry";

type Point = [number, number, number];

export const sceneContent = (preset: CameraPreset, terrainReady: boolean) =>
  preset === "orbit" ? "moon" : terrainReady ? "terrain" : "pending";

/** Camera frame is fixed to terrain zenith/north, independent of epoch or Sun. */
export function terrainCameraPose(preset: CameraPreset, geometry?: TerrainGeometryMetadata | null) {
  const north = geometry ? skyDirectionToTerrainAxes(0, 0, geometry) : { x: 0, y: 0, z: -1 };
  const length = Math.hypot(north.x, north.z) || 1;
  const x = north.x / length, z = north.z / length;
  return {
    up: [0, 1, 0] as Point,
    position: (preset === "south-pole" ? [-x * 206, 128, -z * 206]
      : preset === "surface" ? [-x * 0.38, 0.052, -z * 0.38]
      : [0, 0.35, 6.4]) as Point,
    target: (preset === "south-pole" ? [0, -10, 0]
      : preset === "surface" ? [0, 0.018, 0] : [0, 0, 0]) as Point,
    fov: preset === "surface" ? 68 : preset === "south-pole" ? 44 : 36,
  };
}
