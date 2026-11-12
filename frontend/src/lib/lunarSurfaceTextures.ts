import {
  DataTexture,
  LinearMipmapLinearFilter,
  LinearFilter,
  RepeatWrapping,
  RGBAFormat,
  SRGBColorSpace,
  UnsignedByteType,
} from "three";

export type LunarSurfaceTextures = {
  albedo: DataTexture;
  microRelief: DataTexture;
};

let cachedTextures: LunarSurfaceTextures | null = null;

function fract(value: number) {
  return value - Math.floor(value);
}

function hash2(x: number, y: number) {
  return fract(Math.sin(x * 127.1 + y * 311.7) * 43_758.545_312_3);
}

function smooth(value: number) {
  return value * value * (3 - 2 * value);
}

function valueNoise(x: number, y: number) {
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const tx = smooth(fract(x));
  const ty = smooth(fract(y));
  const a = hash2(x0, y0);
  const b = hash2(x0 + 1, y0);
  const c = hash2(x0, y0 + 1);
  const d = hash2(x0 + 1, y0 + 1);
  return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty;
}

function wrappedDistance(a: number, b: number) {
  const distance = Math.abs(a - b);
  return Math.min(distance, 1 - distance);
}

/**
 * Builds deterministic, tileable lunar albedo and bump textures.
 *
 * The bump texture is decorative micro-normal detail only. Scientific terrain,
 * picking, horizon clearance and suitability calculations continue to use the
 * NASA DEM geometry without modification.
 */
export function getLunarSurfaceTextures(): LunarSurfaceTextures {
  if (cachedTextures) return cachedTextures;

  const size = 512;
  const albedoBytes = new Uint8Array(size * size * 4);
  const reliefBytes = new Uint8Array(size * size * 4);
  const craters = Array.from({ length: 22 }, (_, index) => ({
    x: hash2(index + 17, 2),
    y: hash2(index + 31, 7),
    radius: 0.018 + hash2(index + 5, 13) * 0.058,
    depth: 0.11 + hash2(index + 41, 19) * 0.13,
  }));

  for (let row = 0; row < size; row += 1) {
    const v = row / size;
    for (let column = 0; column < size; column += 1) {
      const u = column / size;
      let broadNoise = 0;
      let amplitude = 0.52;
      let frequency = 4;
      for (let octave = 0; octave < 5; octave += 1) {
        broadNoise += (valueNoise(u * frequency, v * frequency) - 0.5) * amplitude;
        frequency *= 2.03;
        amplitude *= 0.5;
      }

      let relief = broadNoise * 0.34;
      let albedoVariation = broadNoise * 0.2;
      for (const crater of craters) {
        const dx = wrappedDistance(u, crater.x);
        const dy = wrappedDistance(v, crater.y);
        const distance = Math.hypot(dx, dy);
        const normalized = distance / crater.radius;
        if (normalized < 1) {
          const bowl = (1 - normalized * normalized) * crater.depth;
          relief -= bowl;
          albedoVariation -= bowl * 0.13;
        }
        const rimWidth = 0.12;
        const rimDistance = (normalized - 1) / rimWidth;
        if (Math.abs(rimDistance) < 3) {
          const rim = Math.exp(-rimDistance * rimDistance) * crater.depth * 0.72;
          relief += rim;
          albedoVariation += rim * 0.08;
        }
      }

      const albedo = Math.max(0, Math.min(1, 0.55 + albedoVariation));
      const height = Math.max(0, Math.min(1, 0.5 + relief));
      const offset = (row * size + column) * 4;
      albedoBytes[offset] = Math.round(albedo * 184);
      albedoBytes[offset + 1] = Math.round(albedo * 181);
      albedoBytes[offset + 2] = Math.round(albedo * 174);
      albedoBytes[offset + 3] = 255;
      const heightByte = Math.round(height * 255);
      reliefBytes[offset] = heightByte;
      reliefBytes[offset + 1] = heightByte;
      reliefBytes[offset + 2] = heightByte;
      reliefBytes[offset + 3] = 255;
    }
  }

  const albedo = new DataTexture(
    albedoBytes,
    size,
    size,
    RGBAFormat,
    UnsignedByteType,
  );
  albedo.colorSpace = SRGBColorSpace;
  albedo.wrapS = RepeatWrapping;
  albedo.wrapT = RepeatWrapping;
  albedo.minFilter = LinearMipmapLinearFilter;
  albedo.magFilter = LinearFilter;
  albedo.anisotropy = 8;
  albedo.needsUpdate = true;

  const microRelief = new DataTexture(
    reliefBytes,
    size,
    size,
    RGBAFormat,
    UnsignedByteType,
  );
  microRelief.wrapS = RepeatWrapping;
  microRelief.wrapT = RepeatWrapping;
  microRelief.minFilter = LinearMipmapLinearFilter;
  microRelief.magFilter = LinearFilter;
  microRelief.anisotropy = 8;
  microRelief.needsUpdate = true;

  cachedTextures = { albedo, microRelief };
  return cachedTextures;
}
