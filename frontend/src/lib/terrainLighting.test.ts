import { describe, expect, it, vi } from "vitest";
import { DirectionalLight, Vector3, WebGLRenderTarget } from "three";
import { terrainShadowHalfSize, terrainShadowVerticalHalfSize, updateTerrainShadow, TERRAIN_SHADOW_SIZE } from "./terrainLighting";
import type { TerrainMeshData } from "./terrainGeometry";

describe("terrain shadow coverage", () => {
  it("rebuilds projection after distant LODs load instead of keeping the original narrow stripe", () => {
    const light = new DirectionalLight();
    updateTerrainShadow(light, 2);
    const before = light.shadow.camera.projectionMatrix.clone();
    updateTerrainShadow(light, 320);
    expect(light.shadow.camera.projectionMatrix.equals(before)).toBe(false);
    const edge = new Vector3(300, 0, -720).applyMatrix4(light.shadow.camera.projectionMatrix);
    expect(Math.abs(edge.x)).toBeLessThan(1);
    expect(Math.abs(edge.z)).toBeLessThan(1);
  });
  it("reallocates an old-sized shadow texture rather than sampling it as a different resolution", () => {
    const light = new DirectionalLight();
    const old = new WebGLRenderTarget(2048, 2048);
    const dispose = vi.spyOn(old, "dispose");
    light.shadow.map = old;
    updateTerrainShadow(light, 320);
    expect(dispose).toHaveBeenCalledOnce();
    expect(light.shadow.map).toBeNull();
    expect(light.shadow.mapSize.toArray()).toEqual([TERRAIN_SHADOW_SIZE,TERRAIN_SHADOW_SIZE]);
    expect(light.shadow.needsUpdate).toBe(true);
  });
  it("contains the far ring under rotating grazing sunlight, including curved negative terrain", () => {
    const mesh = { widthSceneUnits: 600, depthSceneUnits: 600, minYSceneUnits: -30, maxYSceneUnits: 12 } as TerrainMeshData;
    const size = terrainShadowHalfSize([mesh]);
    for (const azimuth of [0, .7, 1.5, 3, 5]) {
      const direction = new Vector3(Math.sin(azimuth), -.02, Math.cos(azimuth)).normalize();
      const right = new Vector3().crossVectors(new Vector3(0,1,0),direction).normalize();
      const up = new Vector3().crossVectors(direction,right);
      for (let angle=0; angle<Math.PI*2; angle+=.13) for (const y of [-30,12]) {
        const point = new Vector3(300*Math.sin(angle),y,300*Math.cos(angle));
        expect(Math.abs(point.dot(right))).toBeLessThan(size);
        expect(Math.abs(point.dot(up))).toBeLessThan(size);
      }
    }
  });
  it("fits grazing light vertically without clipping curved terrain or wasting a square map", () => {
    const mesh = { widthSceneUnits: 600, depthSceneUnits: 600, minYSceneUnits: -30, maxYSceneUnits: 12 } as TerrainMeshData;
    for (const sunY of [-1, -.7, -.02, 0, .02, .7, 1]) {
      const verticalSize = terrainShadowVerticalHalfSize([mesh], sunY);
      for (let angle = 0; angle < Math.PI * 2; angle += .13) for (const y of [-30.012, 12]) {
        const lightSpaceY = -300 * Math.cos(angle) * sunY + y * Math.sqrt(1 - sunY * sunY);
        expect(Math.abs(lightSpaceY)).toBeLessThan(verticalSize);
      }
      const light = new DirectionalLight();
      updateTerrainShadow(light, terrainShadowHalfSize([mesh]), verticalSize);
      const edge = new Vector3(0, verticalSize * .99, -720).applyMatrix4(light.shadow.camera.projectionMatrix);
      expect(Math.abs(edge.y)).toBeLessThan(1);
    }
    expect(terrainShadowVerticalHalfSize([mesh], .02)).toBeLessThan(terrainShadowHalfSize([mesh]) / 8);
  });
});
