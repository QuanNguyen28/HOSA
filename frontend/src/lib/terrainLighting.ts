import type { DirectionalLight } from "three";
import type { TerrainMeshData } from "./terrainGeometry";

export const TERRAIN_SHADOW_SIZE = 4096;
/** Near shadow cascade around the observer (see DynamicTerrain). */
export const NEAR_SHADOW_SIZE = 2048;

/** Enclose all rendered circular LODs, including their curved vertical extent. */
export function terrainShadowHalfSize(meshes: Array<TerrainMeshData | null | undefined>) {
  return Math.max(1, ...meshes.flatMap((mesh) => mesh ? [Math.hypot(
    Math.min(mesh.widthSceneUnits, mesh.depthSceneUnits)/2,
    Math.max(Math.abs(mesh.minYSceneUnits), Math.abs(mesh.maxYSceneUnits)),
  )] : []))*1.04;
}

/** Light-space height of the circular terrain, rather than a wasteful square. */
export function terrainShadowVerticalHalfSize(
  meshes: Array<TerrainMeshData | null | undefined>, sunY: number,
) {
  const vertical = Math.min(1, Math.abs(sunY));
  const horizontal = Math.sqrt(1 - vertical * vertical);
  return Math.max(1, ...meshes.flatMap((mesh) => mesh ? [
    Math.min(mesh.widthSceneUnits, mesh.depthSceneUnits) / 2 * vertical +
    (Math.max(Math.abs(mesh.minYSceneUnits), Math.abs(mesh.maxYSceneUnits)) + 0.012) * horizontal,
  ] : [])) * 1.04;
}

/** Three.js does not rebuild a shadow camera projection when its bounds mutate. */
export function updateTerrainShadow(
  light: DirectionalLight, halfSize: number, verticalHalfSize = halfSize, mapSize = TERRAIN_SHADOW_SIZE,
) {
  const { shadow } = light;
  Object.assign(shadow.camera, { left: -halfSize, right: halfSize, top: verticalHalfSize,
    bottom: -verticalHalfSize, near: 1, far: 1600 });
  shadow.camera.updateProjectionMatrix();
  shadow.mapSize.set(mapSize, mapSize);
  if (shadow.map && (shadow.map.width !== mapSize || shadow.map.height !== mapSize)) {
    shadow.map.dispose();
    shadow.map = null;
  }
  shadow.needsUpdate = true;
}
