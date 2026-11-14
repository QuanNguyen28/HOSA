/**
 * Moon globe shading ported from the CLPS Lunar Mission Browser
 * (github.com/BroBYW/CLPS-Lunar-Mission-Website, web/src/globe/moonViewer.ts),
 * which renders the Moon Trek mosaic with CesiumJS in display (sRGB) space,
 * without HDR or tone mapping. Cesium's GlobeFS (ENABLE_DAYNIGHT_SHADING):
 *
 *     colour = photo × clamp(5 · max(N·L, 0) + 0.3, 0, 1)
 *
 * Day side = the NASA mosaic as recorded, night side = 30 % of it, a
 * terminator about 8° wide. Cesium uses the smooth ellipsoid normal; here the
 * LOLA bump-mapped normal is kept so the globe's relief is unchanged.
 *
 * Three.js shades in linear light, so the rule is evaluated on sRGB values and
 * converted back with sRGBTransferEOTF; materials using it must set
 * toneMapped={false}. Space is black.
 */
export const SPACE_COLOR = "#000000";

export const GLOBE_DAY_NIGHT = { lambertScale: 5, nightFloor: 0.3 } as const;

const glsl = (value: number) => value.toFixed(4);

function globeLight() {
  const { lambertScale, nightFloor } = GLOBE_DAY_NIGHT;
  return `clamp(${glsl(lambertScale)} * max(dot(normal, directionalLights[ 0 ].direction), 0.0) + ${glsl(nightFloor)}, 0.0, 1.0)`;
}

/** Globe imagery: Cesium's day/night rule. The Sun must be the only directional light. */
export function withGlobeDayNight(fragmentShader: string) {
  return fragmentShader.replace(
    "#include <opaque_fragment>",
    `#if NUM_DIR_LIGHTS > 0
      vec3 referencePhoto = sRGBTransferOETF(vec4(diffuseColor.rgb, 1.0)).rgb;
      outgoingLight = sRGBTransferEOTF(vec4(referencePhoto * ${globeLight()}, 1.0)).rgb;
    #endif
    #include <opaque_fragment>`,
  );
}
