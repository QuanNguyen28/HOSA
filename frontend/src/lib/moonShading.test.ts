import { ShaderLib } from "three";
import { describe, expect, it } from "vitest";

import { withGlobeDayNight } from "./moonShading";

describe("reference moon globe shading", () => {
  it("uses Cesium's day/night rule on the globe", () => {
    const shader = withGlobeDayNight(ShaderLib.physical.fragmentShader);
    expect(shader).toContain("clamp(5.0000 * max(dot(normal, directionalLights[ 0 ].direction), 0.0) + 0.3000, 0.0, 1.0)");
    expect(shader.indexOf("referencePhoto")).toBeLessThan(shader.indexOf("#include <opaque_fragment>"));
  });
});
