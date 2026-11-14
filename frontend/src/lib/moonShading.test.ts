import { ShaderChunk, ShaderLib } from "three";
import { describe, expect, it } from "vitest";

import { withGlobeDayNight, withTerrainDayNight } from "./moonShading";

describe("reference moon globe shading", () => {
  it("uses Cesium's day/night rule on the globe", () => {
    const shader = withGlobeDayNight(ShaderLib.physical.fragmentShader);
    expect(shader).toContain("clamp(5.0000 * max(dot(normal, directionalLights[ 0 ].direction), 0.0) + 0.3000, 0.0, 1.0)");
    expect(shader.indexOf("referencePhoto")).toBeLessThan(shader.indexOf("#include <opaque_fragment>"));
  });

  it("shows terrain photos sunlit at 100% and in shadow at 30%, with the near cascade", () => {
    const shader = withTerrainDayNight(ShaderLib.physical.fragmentShader, ShaderChunk.lights_fragment_begin);
    expect(shader).toContain("terrainShadow[ i ] = directLight.color.r / max( directionalLights[ i ].color.r, 1e-6 );");
    expect(shader).toContain("mix(terrainShadow[ 0 ], terrainShadow[ 1 ],");
    expect(shader).toContain("terrainSunVisible * smoothstep(0.0, 0.0300, dot(normal, directionalLights[ 0 ].direction))");
    expect(shader).toContain("referencePhoto * mix(0.3000, 1.0, terrainDay)");
    expect(shader).not.toContain("#include <lights_fragment_begin>");
  });
});
