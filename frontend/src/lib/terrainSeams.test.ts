import { ShaderLib } from "three";
import { describe, expect, it } from "vitest";

import { RING_SEAM, ringFade, ringTuck, withRingFade } from "./terrainSeams";

describe("nested terrain ring seams", () => {
  it("sinks a coarse ring only under the finer ring and keeps true height at its edge", () => {
    const inner = 6, tuck = 0.04;
    expect(ringTuck(0.5 * inner, inner, tuck)).toBeCloseTo(tuck);
    expect(ringTuck(RING_SEAM.tuckFull * inner, inner, tuck)).toBeCloseTo(tuck);
    expect(ringTuck(RING_SEAM.tuckEnd * inner, inner, tuck)).toBe(0);
    expect(ringTuck(inner, inner, tuck)).toBe(0);
    expect(ringTuck(2 * inner, inner, tuck)).toBe(0);
    const mid = ringTuck(((RING_SEAM.tuckFull + RING_SEAM.tuckEnd) / 2) * inner, inner, tuck);
    expect(mid).toBeGreaterThan(0);
    expect(mid).toBeLessThan(tuck);
    expect(ringTuck(1, 0, tuck)).toBe(0);
  });

  it("fades a ring out over its outer band, finishing inside its cut edge", () => {
    const [start, end] = ringFade(24, 0.12);
    expect(start).toBeCloseTo(RING_SEAM.fadeStart * 24);
    expect(end).toBeCloseTo(24 - 0.18);
    expect(end).toBeGreaterThan(start);
    // The fine ring stays opaque wherever the coarse ring is still tucked.
    expect(start).toBeGreaterThanOrEqual(RING_SEAM.tuckEnd * 24);
  });

  it("scales the material alpha by the fade band in the shaders", () => {
    const shader = { vertexShader: ShaderLib.physical.vertexShader, fragmentShader: ShaderLib.physical.fragmentShader };
    withRingFade(shader);
    expect(shader.vertexShader).toContain("vRingRadius = length(position.xz);");
    expect(shader.fragmentShader).toContain("uniform vec2 ringFade;");
    expect(shader.fragmentShader).toContain("diffuseColor.a *= 1.0 - smoothstep(ringFade.x, ringFade.y, vRingRadius);");
  });
});
