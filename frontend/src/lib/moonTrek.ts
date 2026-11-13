/** Display imagery coordinates only. No terrain, ephemeris or mission decisions. */
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

export function southPolarXY(latitude: number, longitude: number): [number, number] {
  const lon = longitude * Math.PI / 180;
  const rho = 2 * 1_737_400 * Math.tan(Math.PI / 4 + latitude * Math.PI / 360);
  return [rho * Math.sin(lon), rho * Math.cos(lon)];
}

export function polarAtlas(layers: TrekLayer[], x: number, y: number, radius: number): AtlasPlan | null {
  // NAC is used only where the complete requested square has source coverage.
  const layer = ["nac-south", "wac-south"].map(id => layers.find(l => l.id === id)).find(l => l &&
    x-radius >= l.extent[0] && y-radius >= l.extent[1] && x+radius <= l.extent[2] && y+radius <= l.extent[3]);
  if (!layer) return null;
  for (const matrix of [...layer.matrices].reverse()) {
    const span = matrix.resolution * matrix.tile_size;
    const c0 = Math.floor((x-radius-matrix.origin[0]) / span), c1 = Math.floor((x+radius-matrix.origin[0]) / span);
    const r0 = Math.floor((matrix.origin[1]-y-radius) / span), r1 = Math.floor((matrix.origin[1]-y+radius) / span);
    const rows = r1-r0+1, columns = c1-c0+1;
    if (rows*columns > 16 || c0 < 0 || r0 < 0 || c1 >= matrix.width || r1 >= matrix.height) continue;
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
