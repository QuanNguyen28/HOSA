import { ShaderChunk, ShaderLib } from "three";
import { describe, expect, it } from "vitest";

import {
  displayLuminance,
  earthshineStrength,
  meanLitLuminance,
  withGlobeDayNight,
  withTerrainLighting,
} from "./moonShading";

const fragment = ShaderLib.physical.fragmentShader;

describe("reference moon shading", () => {
  it("uses Cesium's day/night rule on the globe", () => {
    const shader = withGlobeDayNight(fragment);
    expect(shader).toContain("clamp(5.0000 * max(dot(normal, directionalLights[ 0 ].direction), 0.0) + 0.3000, 0.0, 1.0)");
    expect(shader.indexOf("referencePhoto")).toBeLessThan(shader.indexOf("#include <opaque_fragment>"));
  });

  it("captures the Sun's shadow and applies the terrain formula", () => {
    const shader = withTerrainLighting(fragment, ShaderChunk.lights_fragment_begin, 0.4);
    expect(shader).toContain("float referenceShadow[ 2 ] = float[ 2 ]( 1.0, 1.0 );");
    expect(shader).toContain("referenceShadow[ i ] = directLight.color.r / max( directionalLights[ i ].color.r, 1e-6 );");
    expect(shader).toContain("mix(referenceShadow[ 0 ], referenceShadow[ 1 ], referenceNearWeight)");
    expect(shader).toContain("clamp(referenceLuma / 0.4000, 0.9550, 1.0450)");
    expect(shader).toContain("directionalLights[ 2 ].color.r");
    expect(shader).toContain("vec3(0.6200, 0.6000, 0.5600) * referenceDetail");
    expect(shader).toContain("(1.6000 * referenceSun + referenceFill + 0.0220)");
    expect(shader).not.toContain("#include <lights_fragment_begin>");
  });

  it("scales earthshine with the Earth's phase", () => {
    expect(earthshineStrength({ x: 1, y: 0, z: 0 }, { x: -2, y: 0, z: 0 })).toBeCloseTo(0.07);
    expect(earthshineStrength({ x: 1, y: 0, z: 0 }, { x: 0, y: 3, z: 0 })).toBeCloseTo(0.035);
    expect(earthshineStrength({ x: 1, y: 0, z: 0 }, { x: 1, y: 0, z: 0 })).toBeCloseTo(0);
  });

  it("measures colours in display space", () => {
    expect(displayLuminance("#ffffff")).toBeCloseTo(1);
    expect(meanLitLuminance([0, 0, 0, 255, 128, 128, 128, 255])).toBeCloseTo(128 / 255);
  });
});
