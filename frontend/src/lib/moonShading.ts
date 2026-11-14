/**
 * Moon shading ported from the CLPS Lunar Mission Browser
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
 * Pole and Ground use the same day/night ratio on their terrain, with the
 * terrain shadow maps deciding what is lit: ground the Sun cannot reach (cast
 * shadow or facing away) keeps 30 % of its sunlit colour, at the Moon view's
 * brightness. Near the pole the NASA mosaic was itself imaged in shadow (at
 * fine zoom 0–13 % of its pixels are lit), so, as in the CLPS terrain, the
 * colour is a fixed regolith albedo; the texture only varies it by ±10 %.
 * DEM relief from a 45° light toward the Sun's azimuth scales day and night,
 * so shadowed ground shows its craters instead of a flat grey veil.
 *
 * Three.js shades in linear light, so the rule is evaluated on sRGB values and
 * converted back with sRGBTransferEOTF; materials using it must set
 * toneMapped={false}. Space is black.
 */
export const SPACE_COLOR = "#000000";

export const DAY_NIGHT = { lambertScale: 5, nightFloor: 0.3 } as const;

export const TERRAIN_DISPLAY = {
  /** Sunlit flat ground (display values), the CLPS regolith hue at the Moon view's day level. */
  albedo: [0.35, 0.339, 0.316],
  /** Texture variation of the albedo, either way. */
  detail: 0.1,
  reliefMix: 0.45,
  reliefMin: 0.5,
  reliefMax: 1.25,
  /** Mean lit display value of the Moon Trek south-pole NAC mosaic (measured). */
  polarMosaicMean: 0.37,
} as const;

const glsl = (value: number) => value.toFixed(4);

/** Day/night factor for directional light 0 (the Sun), scaled by its visibility. */
function dayNightLight(visibility = "1.0") {
  const { lambertScale, nightFloor } = DAY_NIGHT;
  return `clamp(${glsl(lambertScale)} * max(dot(normal, directionalLights[ 0 ].direction), 0.0) * ${visibility} + ${glsl(nightFloor)}, 0.0, 1.0)`;
}

function applyDayNight(visibility?: string) {
  return `#if NUM_DIR_LIGHTS > 0
      vec3 referencePhoto = sRGBTransferOETF(vec4(diffuseColor.rgb, 1.0)).rgb;
      outgoingLight = sRGBTransferEOTF(vec4(referencePhoto * ${dayNightLight(visibility)}, 1.0)).rgb;
    #endif
    #include <opaque_fragment>`;
}

/** Globe imagery: Cesium's day/night rule. The Sun must be the only directional light. */
export function withGlobeDayNight(fragmentShader: string) {
  return fragmentShader.replace("#include <opaque_fragment>", applyDayNight());
}

const SHADOW_STATEMENT =
  /(directLight\.color \*= \( directLight\.visible && receiveShadow \) \? getShadow\( directionalShadowMap\[ i \][^;]*;)/;

/**
 * Terrain: the Moon view's day/night ratio with the Sun's visibility from the
 * terrain shadow maps, a fixed albedo and DEM relief. Directional lights must
 * be, in order: 0 the Sun with the wide shadow map, 1 the Sun with the near
 * shadow cascade (used inside its bounds, the wide one elsewhere).
 * `textureMean` is the mean display luminance of the material's texture.
 */
export function withTerrainDayNight(fragmentShader: string, lightsChunk: string, textureMean: number) {
  if (!SHADOW_STATEMENT.test(lightsChunk)) throw new Error("Unsupported Three.js light chunk");
  const { nightFloor } = DAY_NIGHT;
  const { albedo, detail, reliefMix, reliefMin, reliefMax } = TERRAIN_DISPLAY;
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
        vec3 referenceBase = vec3(${albedo.map(glsl).join(", ")})
          * clamp(referenceLuma / ${glsl(textureMean)}, ${glsl(1 - detail)}, ${glsl(1 + detail)});
        vec3 referenceUp = normalize((viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
        vec3 referenceL = directionalLights[ 0 ].direction;
        vec3 referenceLh = referenceL - dot(referenceL, referenceUp) * referenceUp;
        referenceLh = dot(referenceLh, referenceLh) > 1e-6 ? normalize(referenceLh) : vec3(0.0);
        vec3 referenceF = normalize(referenceLh + referenceUp);
        float referenceRelief = clamp(dot(normal, referenceF) / max(dot(referenceUp, referenceF), 1e-3), 0.0, 2.0);
        referenceRelief = clamp(mix(1.0, referenceRelief, ${glsl(reliefMix)}), ${glsl(reliefMin)}, ${glsl(reliefMax)});
        float referenceDay = referenceSunVisible * smoothstep(0.0, 0.02, dot(normal, referenceL));
        float referenceLight = mix(${glsl(nightFloor)}, 1.0, referenceDay) * referenceRelief;
        outgoingLight = sRGBTransferEOTF(vec4(clamp(referenceBase * referenceLight, 0.0, 1.0), 1.0)).rgb;
      #endif
      #include <opaque_fragment>`,
    );
}
