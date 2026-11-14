import { ShaderChunk, ShaderLib } from "three";
import { describe, expect, it } from "vitest";

import { withGlobeDayNight, withTerrainDayNight } from "./moonShading";

const fragment = ShaderLib.physical.fragmentShader;

describe("Moon day/night shading", () => {
  it("uses Cesium's day/night rule on the globe", () => {
    const shader = withGlobeDayNight(fragment);
    expect(shader).toContain("clamp(5.0000 * max(dot(normal, directionalLights[ 0 ].direction), 0.0) * 1.0 + 0.3000, 0.0, 1.0)");
    expect(shader.indexOf("referencePhoto")).toBeLessThan(shader.indexOf("#include <opaque_fragment>"));
  });

  it("keeps 30% of the sunlit colour in terrain shadow, with relief", () => {
    const shader = withTerrainDayNight(fragment, ShaderChunk.lights_fragment_begin, 0.37);
    expect(shader).toContain("float referenceShadow[ 2 ] = float[ 2 ]( 1.0, 1.0 );");
    expect(shader).toContain("referenceShadow[ i ] = directLight.color.r / max( directionalLights[ i ].color.r, 1e-6 );");
    expect(shader).toContain("mix(referenceShadow[ 0 ], referenceShadow[ 1 ], referenceNearWeight)");
    expect(shader).toContain("vec3(0.3500, 0.3390, 0.3160)");
    expect(shader).toContain("clamp(referenceLuma / 0.3700, 0.9000, 1.1000)");
    expect(shader).toContain("mix(0.3000, 1.0, referenceDay) * referenceRelief");
    expect(shader).not.toContain("#include <lights_fragment_begin>");
  });

});
