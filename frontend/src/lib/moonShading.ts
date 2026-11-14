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

/** Terrain: N·L (≈ sine of the Sun's height over the slope) over which ground goes from shadow to sunlit. */
export const TERRAIN_DAY = { edge: 0.03 } as const;

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

const SHADOW_STATEMENT =
  /(directLight\.color \*= \( directLight\.visible && receiveShadow \) \? getShadow\( directionalShadowMap\[ i \][^;]*;)/;

/**
 * Pole/Ground terrain: the Moon view's day/night look on the terrain photo.
 * The photo is shown with its own contrast (no lighting model or tone mapping
 * softening it): sunlit ground as recorded, ground the mission-time Sun cannot
 * reach – terrain shadow map or facing away – at 30 %, like the Moon view's
 * night side. Directional light 0 must be the Sun with the wide terrain
 * shadow map; light 1, if it casts a shadow, the same Sun's near cascade.
 */
export function withTerrainDayNight(fragmentShader: string, lightsChunk: string) {
  if (!SHADOW_STATEMENT.test(lightsChunk)) throw new Error("Unsupported Three.js light chunk");
  const lights = lightsChunk.replace(
    SHADOW_STATEMENT,
    `$1
    #if UNROLLED_LOOP_INDEX < 2
      terrainShadow[ i ] = directLight.color.r / max( directionalLights[ i ].color.r, 1e-6 );
    #endif`,
  );
  return fragmentShader
    .replace(
      "#include <lights_fragment_begin>",
      `float terrainShadow[ 2 ] = float[ 2 ]( 1.0, 1.0 );\n${lights}
      float terrainSunVisible = terrainShadow[ 0 ];
      #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 1
        // Inside the near cascade (light 1) its finer shadow map decides.
        vec3 terrainNearCoord = vDirectionalShadowCoord[ 1 ].xyz / vDirectionalShadowCoord[ 1 ].w;
        vec2 terrainNearEdge = min(terrainNearCoord.xy, 1.0 - terrainNearCoord.xy);
        terrainSunVisible = mix(terrainShadow[ 0 ], terrainShadow[ 1 ],
          smoothstep(0.0, 0.06, min(terrainNearEdge.x, terrainNearEdge.y)));
      #endif`,
    )
    .replace(
      "#include <opaque_fragment>",
      `#if NUM_DIR_LIGHTS > 0
        vec3 referencePhoto = sRGBTransferOETF(vec4(diffuseColor.rgb, 1.0)).rgb;
        // The polar Sun grazes the ground, so 5 · N·L (the globe's terminator
        // ramp) would leave flat sunlit ground at ~0.4, barely above shadow.
        // Ground the Sun reaches shows the photo as recorded instead.
        float terrainDay = terrainSunVisible * smoothstep(0.0, ${glsl(TERRAIN_DAY.edge)}, dot(normal, directionalLights[ 0 ].direction));
        outgoingLight = sRGBTransferEOTF(vec4(referencePhoto * mix(${glsl(GLOBE_DAY_NIGHT.nightFloor)}, 1.0, terrainDay), 1.0)).rgb;
      #endif
      #include <opaque_fragment>`,
    );
}
