/**
 * Seamless nested terrain rings (Pole and Ground).
 *
 * Each coarser ring used to be lowered as a whole (1.5–12 m) so the finer ring
 * drew on top. That left a step at every ring edge – at a ~1° Sun a 12 m step
 * throws a ~600 m shadow line – plus a hard change of image and mesh detail.
 * Instead, as in the CLPS terrain, only the part of a coarse ring that lies
 * under the finer ring sinks ("tucks"), so outside it the coarse ring keeps its
 * true height, and the finer ring fades out (alpha) over its outer band so
 * detail and imagery blend into the coarse ring. Rings draw coarse to fine
 * (`renderOrder`), so each fade blends over the ring already drawn below it.
 */
export const RING_SEAM = {
  /** Coarse ring triangles start this far inside the finer ring (fraction of its radius). */
  overlapStart: 0.9,
  /** Coarse vertices are fully tucked inside this radius and back at true height by `tuckEnd`. */
  tuckFull: 0.93,
  tuckEnd: 0.955,
  /** The finer ring is opaque inside this radius, then fades out towards its edge. */
  fadeStart: 0.955,
} as const;

/** Tuck depth (scene km) for rings 1..5 (6 km … 300 km), deeper for coarser rings. */
export const RING_TUCK_KM = [0.02, 0.04, 0.06, 0.2, 0.4] as const;

const smoothstep = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** How far (scene units) to sink a coarse-ring vertex at radius r under a finer ring of radius inner. */
export function ringTuck(r: number, inner: number, tuck: number) {
  if (inner <= 0 || tuck <= 0) return 0;
  return tuck * (1 - smoothstep(RING_SEAM.tuckFull * inner, RING_SEAM.tuckEnd * inner, r));
}

/** Fade band [start, end] (scene units) for a ring of the given outer radius and cell spacing. */
export function ringFade(outer: number, spacing: number): [number, number] {
  return [RING_SEAM.fadeStart * outer, Math.max(RING_SEAM.fadeStart * outer, outer - 1.5 * spacing)];
}

/** Shader edits: fade a ring's alpha out between radii `ringFade.x` and `ringFade.y` (needs a transparent material). */
export function withRingFade(shader: { vertexShader: string; fragmentShader: string }) {
  shader.vertexShader = "varying float vRingRadius;\n" + shader.vertexShader.replace(
    "#include <begin_vertex>",
    "#include <begin_vertex>\n  vRingRadius = length(position.xz);",
  );
  shader.fragmentShader = "uniform vec2 ringFade;\nvarying float vRingRadius;\n" + shader.fragmentShader.replace(
    "#include <alphamap_fragment>",
    `#include <alphamap_fragment>
    if (ringFade.y > ringFade.x) diffuseColor.a *= 1.0 - smoothstep(ringFade.x, ringFade.y, vRingRadius);`,
  );
}
