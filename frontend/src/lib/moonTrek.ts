/** Display imagery coordinates only. No terrain, ephemeris or mission decisions. */
import { Vector3 } from 'three';
import { coordinateToVector, MOON_SCENE_RADIUS } from './lunar';

export type TrekMatrix = { level: number; width: number; height: number; tile_size: number; origin: [number, number]; resolution: number };
export type TrekLayer = { id: string; label: string; title: string; provider: string; projection: "equirectangular" | "south_polar";
  extent: [number, number, number, number]; radius_m: number; matrices: TrekMatrix[]; native_resolution_m: number;
  observation_note: string; capabilities_url: string };
export type TrekCatalog = { layers: TrekLayer[]; documentation_url: string };
export type TrekTile = { level: number; row: number; column: number };
export type AtlasPlan = { layer: TrekLayer; matrix: TrekMatrix; tiles: TrekTile[]; bounds: [number, number, number, number];
  firstRow: number; firstColumn: number; rows: number; columns: number };

export function tileUrl(layer: string, tile: TrekTile) {
  return `/api/lunar/imagery/${layer}/${tile.level}/${tile.row}/${tile.column}`;
}

export function globeBounds(tile: TrekTile) {
  const rows = 2 ** tile.level, columns = rows * 2;
  return { west: -180 + tile.column * 360 / columns, east: -180 + (tile.column + 1) * 360 / columns,
    north: 90 - tile.row * 180 / rows, south: 90 - (tile.row + 1) * 180 / rows };
}

/** What the globe tile selection needs to know about the camera. */
export type GlobeTileView = {
  /** Camera position in scene units (the Moon is centred at the origin). */
  position: Vector3;
  /** Vertical focal length in pixels. */
  focalPx: number;
  maxLevel: number;
  /** Whether a bounding sphere (scene units) intersects the camera frustum. */
  inView: (center: Vector3, radius: number) => boolean;
  /** Tiles allowed beyond the two level-0 roots. */
  budget?: number;
  /** A tile is split while it covers more than this many pixels on screen. */
  splitPixels?: number;
  /** Tiles entirely south of this latitude are left to the polar cap. */
  coveredBelowLat?: number;
};

/** The globe's south polar cap: drawn from the polar mosaic, fading out between these latitudes. */
export const POLAR_CAP = { opaqueLat: -76, edgeLat: -73 } as const;

/** Polar stereographic radius (m) of a southern latitude. */
export function polarRho(latitude: number) {
  return 2 * 1_737_400 * Math.tan(Math.PI / 4 + latitude * Math.PI / 360);
}

/** Polar stereographic point under the camera, pulled into the cap. */
export function polarCapCenter(position: Vector3, capRho = polarRho(POLAR_CAP.edgeLat)): [number, number] {
  const r = position.length() || 1;
  const latitude = Math.asin(position.y / r) * 180 / Math.PI;
  const longitude = Math.atan2(-position.z, position.x) * 180 / Math.PI;
  const [x, y] = southPolarXY(Math.min(latitude, 89), longitude);
  const rho = Math.hypot(x, y);
  return rho > capRho ? [x * capRho / rho, y * capRho / rho] : [x, y];
}

/** LOLA displacement margin around a tile's sphere cap, in scene units. */
const RELIEF_MARGIN = 0.025;

/**
 * Globe tiles to draw, coarse to fine. Only tiles facing the camera and inside
 * its frustum are refined, largest on screen first, so the budget is spent on
 * what is in view: a depth-first split that ignored the frustum used it up on
 * off-screen tiles and left close oblique views on coarse, faceted tiles.
 */
export function selectGlobeTiles(view: GlobeTileView): TrekTile[] {
  const { position, focalPx, maxLevel, inView, budget = 96, splitPixels = 300, coveredBelowLat } = view;
  const direction = position.clone().normalize(), distance = position.length();
  const measure = (tile: TrekTile) => {
    const b = globeBounds(tile), lat = (b.north + b.south) / 2, lon = (b.west + b.east) / 2;
    if (coveredBelowLat !== undefined && tile.level > 0 && b.north <= coveredBelowLat) return null;
    const normal = coordinateToVector({ latitude: lat, longitude: lon }, 1);
    const angle = Math.min(Math.PI / 2, Math.hypot(b.north - b.south, (b.east - b.west) * Math.cos(lat * Math.PI / 180)) * Math.PI / 360);
    if (normal.dot(direction) < MOON_SCENE_RADIUS / distance - Math.sin(angle) - .05) return null;
    const center = normal.multiplyScalar(MOON_SCENE_RADIUS), radius = MOON_SCENE_RADIUS * Math.sin(angle) + RELIEF_MARGIN;
    if (!inView(center, radius)) return null;
    // Size from the nearest point of the tile, so oblique close views refine.
    return 2 * angle * MOON_SCENE_RADIUS * focalPx / Math.max(.02, position.distanceTo(center) - radius);
  };
  const roots: TrekTile[] = [{ level: 0, row: 0, column: 0 }, { level: 0, row: 0, column: 1 }];
  const selected = [...roots];
  const queue: Array<{ tile: TrekTile; pixels: number }> = [];
  for (const tile of roots) {
    const pixels = measure(tile);
    if (pixels !== null) queue.push({ tile, pixels });
  }
  while (queue.length && selected.length - roots.length < budget) {
    let best = 0;
    for (let i = 1; i < queue.length; i++) if (queue[i].pixels > queue[best].pixels) best = i;
    const { tile, pixels } = queue.splice(best, 1)[0];
    if (pixels < splitPixels || tile.level >= maxLevel) continue;
    for (let i = 0; i < 4 && selected.length - roots.length < budget; i++) {
      const child = { level: tile.level + 1, row: tile.row * 2 + Math.floor(i / 2), column: tile.column * 2 + i % 2 };
      const childPixels = measure(child);
      if (childPixels === null) continue;
      selected.push(child);
      queue.push({ tile: child, pixels: childPixels });
    }
  }
  return selected;
}

export function southPolarXY(latitude: number, longitude: number): [number, number] {
  const lon = longitude * Math.PI / 180;
  const rho = 2 * 1_737_400 * Math.tan(Math.PI / 4 + latitude * Math.PI / 360);
  return [rho * Math.sin(lon), rho * Math.cos(lon)];
}

export function polarAtlas(layers: TrekLayer[], x: number, y: number, radius: number, maxTiles = 16): AtlasPlan | null {
  // NAC is used only where the complete requested square has source coverage.
  const layer = ["nac-south", "wac-south"].map(id => layers.find(l => l.id === id)).find(l => l &&
    x-radius >= l.extent[0] && y-radius >= l.extent[1] && x+radius <= l.extent[2] && y+radius <= l.extent[3]);
  if (!layer) return null;
  for (const matrix of [...layer.matrices].reverse()) {
    const span = matrix.resolution * matrix.tile_size;
    const c0 = Math.floor((x-radius-matrix.origin[0]) / span), c1 = Math.floor((x+radius-matrix.origin[0]) / span);
    const r0 = Math.floor((matrix.origin[1]-y-radius) / span), r1 = Math.floor((matrix.origin[1]-y+radius) / span);
    const rows = r1-r0+1, columns = c1-c0+1;
    if (rows*columns > maxTiles || c0 < 0 || r0 < 0 || c1 >= matrix.width || r1 >= matrix.height) continue;
    const tiles: TrekTile[] = [];
    for (let row=r0; row<=r1; row++) for (let column=c0; column<=c1; column++) tiles.push({level:matrix.level,row,column});
    return { layer, matrix, tiles, rows, columns, firstRow:r0, firstColumn:c0,
      bounds:[matrix.origin[0]+c0*span, matrix.origin[1]-(r1+1)*span, matrix.origin[0]+(c1+1)*span, matrix.origin[1]-r0*span] };
  }
  return null;
}

let catalog: Promise<TrekCatalog> | null = null;
export function trekCatalog() {
  if (!catalog) catalog = fetch('/api/lunar/imagery/layers').then(r => {
    if (!r.ok) throw new Error('NASA imagery catalog unavailable');
    return r.json() as Promise<TrekCatalog>;
  }).catch(error => { catalog=null; throw error; });
  return catalog;
}

const images = new Map<string, Promise<HTMLImageElement>>();
const queue: Array<() => void> = [];
let running = 0;
function pump() { while (running < 6 && queue.length) { running++; queue.shift()!(); } }
export function tileImage(url: string): Promise<HTMLImageElement> {
  const cached = images.get(url);
  if (cached) { images.delete(url); images.set(url,cached); return cached; }
  // Rapid camera movement may retire LODs before they load. Keep queued work
  // bounded too; the globe retains its loaded parent tile on a rejected detail.
  if (queue.length >= 192) return Promise.reject(new Error('Imagery detail queue busy'));
  const promise = new Promise<HTMLImageElement>((resolve,reject) => {
    queue.push(() => {
      const image = new Image();
      const done = () => { running--; pump(); };
      image.onload = () => { done(); resolve(image); };
      image.onerror = () => { images.delete(url); done(); reject(new Error('NASA imagery tile unavailable')); };
      image.src = url;
    });
  });
  images.set(url,promise);
  // Browser HTTP cache retains bytes; keep decoded images bounded in memory.
  while (images.size > 128) images.delete(images.keys().next().value!);
  pump();
  return promise;
}
