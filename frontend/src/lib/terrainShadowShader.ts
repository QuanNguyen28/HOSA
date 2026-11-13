import { ShaderChunk } from "three";

/** Compare each PCF tap at the receiver plane's depth at that texel centre.
 * Using one constant receiver depth for all taps creates bands on grazing
 * terrain: adjacent samples of the same slope incorrectly shadow each other.
 */
export function terrainShadowFragment(fragmentShader: string) {
  const chunk = ShaderChunk.shadowmap_pars_fragment;
  const pcfStart = chunk.indexOf("#if defined( SHADOWMAP_TYPE_PCF )");
  const pcfEnd = chunk.indexOf("#elif defined( SHADOWMAP_TYPE_PCF_SOFT )", pcfStart);
  if (pcfStart < 0 || pcfEnd < 0) throw new Error("Unsupported Three.js terrain shadow shader");
  const pcf = chunk.slice(pcfStart, pcfEnd).replace(
    /texture2DCompare\( shadowMap, (.+?), shadowCoord.z \)/g,
    "terrainShadowCompare( shadowMap, $1, shadowCoord.xyz, terrainReceiverGradient, shadowMapSize )",
  );
  const helper = `
    float terrainShadowCompare(sampler2D depths, vec2 uv, vec3 receiver,
      vec2 gradient, vec2 mapSize) {
      vec2 texelCentre = (floor(uv * mapSize) + 0.5) / mapSize;
      float receiverDepth = receiver.z + dot(texelCentre - receiver.xy, gradient);
      return texture2DCompare(depths, uv, receiverDepth);
    }
  `;
  const corrected = (chunk.slice(0, pcfStart) + pcf + chunk.slice(pcfEnd))
    .replace("float getShadow(", `${helper}\nfloat getShadow(`)
    .replace("shadowCoord.z += shadowBias;", `
      // Derivatives must execute before the per-fragment frustum branch.
      vec3 receiverDx = dFdx(shadowCoord.xyz);
      vec3 receiverDy = dFdy(shadowCoord.xyz);
      float determinant = receiverDx.x * receiverDy.y - receiverDx.y * receiverDy.x;
      vec2 terrainReceiverGradient = vec2(0.0);
      float derivativeScale = length(receiverDx.xy) * length(receiverDy.xy);
      if (abs(determinant) > 1e-6 * derivativeScale) {
        terrainReceiverGradient = vec2(
          receiverDx.z * receiverDy.y - receiverDy.z * receiverDx.y,
          receiverDy.z * receiverDx.x - receiverDx.z * receiverDy.x
        ) / determinant;
      }
      shadowCoord.z += shadowBias;
    `);
  return fragmentShader.replace("#include <shadowmap_pars_fragment>", corrected);
}
