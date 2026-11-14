/**
 * Moon shading ported from the CLPS Lunar Mission Browser
 * (github.com/BroBYW/CLPS-Lunar-Mission-Website, web/src/globe/*), which renders
 * with CesiumJS in display (sRGB) space without HDR or tone mapping:
 *
 * - Globe (Cesium GlobeFS, ENABLE_DAYNIGHT_SHADING on an ellipsoid):
 *     colour = photo × clamp(5 · max(N·L, 0) + 0.3, 0, 1)
 *   Day side = the NASA mosaic as recorded, night side = 30 % of it, a
 *   terminator about 8° wide. Cesium uses the smooth ellipsoid normal; here
 *   the LOLA bump-mapped normal is kept so the globe's relief is unchanged.
 * - Terrain (web/src/globe/terrainPatch.ts):
 *     colour = albedo · (1.6 · sun + earthshine + 0.022)
 *     sun = visible · mix(μ0, 2μ0 / (μ0 + μ + 0.05), 0.7) · (0.35 + 0.65 · (0.5 + 0.5 · L·V))
 *     earthshine = 0.07 · (1 − cos phase) / 2 · max(N·E, 0)
 *   with albedo (0.62, 0.60, 0.56).
 * - Space is black.
 *
 * Three.js shades in linear light, so each rule is evaluated on sRGB values
 * and converted back with sRGBTransferEOTF; materials using them must set
 * toneMapped={false}.
 */
export const SPACE_COLOR = "#000000";

export const GLOBE_DAY_NIGHT = { lambertScale: 5, nightFloor: 0.3 } as const;

export const TERRAIN_LIGHT = {
  albedo: [0.62, 0.6, 0.56],
  sunGain: 1.6,
  lommelSeeligerBlend: 0.7,
  ambient: 0.022,
  /** Earthshine at full Earth, as a share of full sunlight on a surface facing it. */
  earthshine: 0.07,
  /** Light and dark patches: ±(0.06 + 0.03) / 2 of the albedo. */
  albedoPatches: 0.045,
} as const;

const glsl = (value: number) => value.toFixed(4);
const vec3 = (value: readonly number[]) => `vec3(${value.map(glsl).join(", ")})`;

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

const SHADOW_STATEMENT =
  /(directLight\.color \*= \( directLight\.visible && receiveShadow \) \? getShadow\( directionalShadowMap\[ i \][^;]*;)/;

/**
 * Terrain: the reference Lunar-Lambert Sun term with terrain shadows, plus
 * earthshine. Directional lights must be, in order: 0 the Sun with the wide
 * shadow map, 1 the Sun with the near shadow cascade, 2 (optional) earthshine
 * with intensity = earthshine strength. Inside the near cascade its shadow is
 * used; elsewhere the wide one.
 *
 * Colour is the reference albedo exactly. The material's own texture only
 * varies it by ±4.5 %, the amplitude of the reference's light and dark
 * patches: `albedoMeanDisplay` is that texture's mean sRGB luminance.
 */
export function withTerrainLighting(
  fragmentShader: string,
  lightsChunk: string,
  albedoMeanDisplay: number,
) {
  const { albedo, sunGain, lommelSeeligerBlend, ambient } = TERRAIN_LIGHT;
  if (!SHADOW_STATEMENT.test(lightsChunk)) throw new Error("Unsupported Three.js light chunk");
  const lights = lightsChunk.replace(
    SHADOW_STATEMENT,
    `$1
    #if UNROLLED_LOOP_INDEX < 2
      referenceShadow[ i ] = directLight.color.r / max( directionalLights[ i ].color.r, 1e-6 );
    #endif`,
  );
  return fragmentShader
    .replace(
      "#include <lights_fragment_begin>",
      `float referenceShadow[ 2 ] = float[ 2 ]( 1.0, 1.0 );\n${lights}
      float referenceSunVisible = referenceShadow[ 0 ];
      #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 1
        vec3 referenceNearCoord = vDirectionalShadowCoord[ 1 ].xyz / vDirectionalShadowCoord[ 1 ].w;
        vec2 referenceNearEdge = min(referenceNearCoord.xy, 1.0 - referenceNearCoord.xy);
        float referenceNearWeight = smoothstep(0.0, 0.06, min(referenceNearEdge.x, referenceNearEdge.y));
        referenceSunVisible = mix(referenceShadow[ 0 ], referenceShadow[ 1 ], referenceNearWeight);
      #endif`,
    )
    .replace(
      "#include <opaque_fragment>",
      `#if NUM_DIR_LIGHTS > 0
        vec3 referenceTexture = sRGBTransferOETF(vec4(diffuseColor.rgb, 1.0)).rgb;
        float referenceLuma = dot(referenceTexture, vec3(0.2126, 0.7152, 0.0722));
        float referenceDetail = clamp(referenceLuma / ${glsl(albedoMeanDisplay)}, ${glsl(1 - TERRAIN_LIGHT.albedoPatches)}, ${glsl(1 + TERRAIN_LIGHT.albedoPatches)});
        vec3 referenceL = directionalLights[ 0 ].direction;
        vec3 referenceV = geometryViewDir;
        float referenceMu0 = dot(normal, referenceL);
        float referenceMu = max(dot(normal, referenceV), 0.0);
        float referenceSun = 0.0;
        if (referenceMu0 > 0.0) {
          float lommelSeeliger = 2.0 * referenceMu0 / (referenceMu0 + referenceMu + 0.05);
          float phase = 0.35 + 0.65 * (0.5 + 0.5 * dot(referenceL, referenceV));
          referenceSun = referenceSunVisible * mix(referenceMu0, lommelSeeliger, ${glsl(lommelSeeligerBlend)}) * phase;
        }
        float referenceFill = 0.0;
        #if NUM_DIR_LIGHTS > 2
          referenceFill = directionalLights[ 2 ].color.r * max(dot(normal, directionalLights[ 2 ].direction), 0.0);
        #endif
        vec3 referenceColor = ${vec3(albedo)} * referenceDetail
          * (${glsl(sunGain)} * referenceSun + referenceFill + ${glsl(ambient)});
        outgoingLight = sRGBTransferEOTF(vec4(clamp(referenceColor, 0.0, 1.0), 1.0)).rgb;
      #endif
      #include <opaque_fragment>`,
    );
}

/** sRGB luminance (0–1) of a #rrggbb colour. */
export function displayLuminance(hex: string) {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  return (0.2126 * ((value >> 16) & 255) + 0.7152 * ((value >> 8) & 255) + 0.0722 * (value & 255)) / 255;
}

type Direction = { x: number; y: number; z: number };

/** Earthshine strength from the reference: 0.07 × the Earth's lit fraction seen from the Moon. */
export function earthshineStrength(sun: Direction, earth: Direction) {
  const sunLength = Math.hypot(sun.x, sun.y, sun.z) || 1;
  const earthLength = Math.hypot(earth.x, earth.y, earth.z) || 1;
  const cosPhase = (sun.x * earth.x + sun.y * earth.y + sun.z * earth.z) / (sunLength * earthLength);
  return (TERRAIN_LIGHT.earthshine * (1 - cosPhase)) / 2;
}

/** Mean sRGB luminance of an 8-bit RGBA image, ignoring near-black (shadowed) pixels. */
export function meanLitLuminance(pixels: ArrayLike<number>, darkCutoff = 0.08) {
  let sum = 0;
  let count = 0;
  for (let offset = 0; offset + 3 < pixels.length; offset += 4) {
    const luma = (0.2126 * pixels[offset] + 0.7152 * pixels[offset + 1] + 0.0722 * pixels[offset + 2]) / 255;
    if (luma < darkCutoff) continue;
    sum += luma;
    count += 1;
  }
  return count ? sum / count : 0.5;
}
