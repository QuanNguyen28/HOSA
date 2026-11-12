export type Site = {
  id: string;
  name: string;
  group: "illumination" | "artemis" | "clps" | "contrast";
  lat: number;
  lon: number;
  kind: "exact" | "approx";
  height_m: number;
  point: string;
  source: string;
  url: string;
  notes?: string;
};

export const GROUPS: Record<Site["group"], string> = {
  illumination: "High-illumination points",
  artemis: "Artemis candidate regions",
  clps: "CLPS landing sites",
  contrast: "Permanent shadow",
};
export const GROUP_ORDER: Site["group"][] = [
  "illumination",
  "artemis",
  "clps",
  "contrast",
];

const A = (
  id: string,
  name: string,
  lat: number,
  lon: number,
  h: number,
): Site => ({
  id,
  name,
  group: "artemis",
  lat,
  lon,
  kind: "approx",
  height_m: h,
  point:
    "Highest LOLA point inside the region footprint (2022 list, served by NASA Moon Trek). lat/lon below is the footprint centroid",
  source: "NASA Moon Trek, A3_Named_regions_SP",
  url: "https://trek.nasa.gov/moon/trekarcgis2/rest/services/A3_Named_regions_SP/MapServer/0",
});

const P = (id: string, name: string, lat: number, lon: number, height_m: number): Site => ({
  id, name, lat, lon, height_m, group: "illumination", kind: "exact",
  point: "Centre pixel of the verified 5 m/pixel LOLA terrain footprint used by HOSA",
  source: "NASA GSFC PGDA Product 78",
  url: "https://pgda.gsfc.nasa.gov/products/78",
});

export const SITES: Site[] = [
  {
    id: "connecting-ridge",
    name: "Connecting ridge",
    group: "illumination",
    lat: -89.4398,
    lon: -137.17,
    kind: "exact",
    height_m: 1958.6,
    point:
      "The published highest-illumination point on the ridge joining Shackleton and de Gerlache",
    source: "Mazarico et al. 2011, Icarus",
    url: "https://doi.org/10.1016/j.icarus.2011.03.007",
  },
  {
    id: "shackleton-rim",
    name: "Shackleton rim",
    group: "illumination",
    lat: -89.6866,
    lon: -162.81,
    kind: "exact",
    height_m: 1729.6,
    point:
      "The published highest-illumination point on the rim of Shackleton crater",
    source: "Mazarico et al. 2011, Icarus",
    url: "https://doi.org/10.1016/j.icarus.2011.03.007",
  },
  {
    ...A(
      "peak-near-cabeus-b",
      "Peak near Cabeus B",
      -83.58392,
      -68.46415,
      4602.1,
    ),
    notes: "Region added in 2024.",
  },
  A("haworth", "Haworth", -86.36428, -23.20814, 2842.2),
  {
    ...A("malapert-massif", "Malapert Massif", -85.98794, 2.06238, 5173.3),
    notes:
      "Intuitive Machines IM-5 plans to land at Mons Malapert (no coordinates published).",
  },
  A("mons-mouton-plateau", "Mons Mouton Plateau", -84.37473, 32.00484, 5605.6),
  A("mons-mouton", "Mons Mouton", -85.40381, 31.70225, 6463.6),
  A("nobile-rim-1", "Nobile Rim 1", -85.23291, 36.59181, 6800),
  A("nobile-rim-2", "Nobile Rim 2", -84.07924, 54.89488, 1817.4),
  A("de-gerlache-rim-2", "de Gerlache Rim 2", -88.58734, -67.89559, 1764.9),
  {
    id: "im1-odysseus",
    name: "IM-1 Odysseus landing site",
    group: "clps",
    lat: -80.13,
    lon: 1.44,
    kind: "exact",
    height_m: 2592,
    point: "Landing point reported after touchdown on 22 February 2024",
    source: "NASA: LRO images Odysseus",
    url: "https://www.nasa.gov/",
  },
  {
    id: "im2-athena",
    name: "IM-2 Athena landing site",
    group: "clps",
    lat: -84.7906,
    lon: 29.1957,
    kind: "exact",
    height_m: 5321.7,
    point: "Landing point reported after touchdown on 6 March 2025",
    source: "LROC image 1408",
    url: "https://www.nasa.gov/",
  },
  {
    id: "viper",
    name: "VIPER mission area",
    group: "clps",
    lat: -85.42088,
    lon: 31.6218,
    kind: "exact",
    height_m: 6417.6,
    point: "Centre of the planned VIPER traverse area on Nobile",
    source: "NASA VIPER",
    url: "https://www.nasa.gov/",
  },
  {
    id: "shackleton-floor",
    name: "Shackleton crater floor",
    group: "contrast",
    lat: -89.62511,
    lon: 118.60583,
    kind: "approx",
    height_m: -2872.3,
    point: "Lowest LOLA point inside the permanently shadowed floor",
    source: "NASA Moon Trek, A3_Named_regions_SP",
    url: "https://trek.nasa.gov/",
  },
  P("peak-near-shackleton", "Peak near Shackleton", -88.81101, 123.69007, 1645.5),
  P("leibnitz-beta-plateau", "Leibnitz Beta Plateau", -85.42658, 31.74276, 6398.9),
  P("de-gerlache-kocher", "de Gerlache–Kocher Massif", -85.82955, -116.32202, 2705.9),
  P("shoemaker", "Shoemaker crater", -87.18351, 62.83501, 548.1),
  P("amundsen-rim", "Amundsen rim", -84.22874, 69.44395, 399.3),
];

export const HEIGHTS = [2, 10, 20, 30];
export const SPEEDS = [1, 6, 24, 72];
export const speedLabel = (h: number) =>
  h >= 24
    ? `${h / 24} day${h > 24 ? "s" : ""} per second`
    : `${h} hour${h > 1 ? "s" : ""} per second`;

export const HOUR = 3600e3;
export const DAY = 24 * HOUR;
export const STEP = 5 * 60e3;
export const MIN_MS = Date.UTC(2024, 0, 1);
export const MAX_MS = Date.UTC(2031, 0, 1);

// Visual preview only. Mission results come from the backend.
function hash(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967296;
}
const rad = Math.PI / 180;
const wrap = (a: number) => ((a % 360) + 360) % 360;
export const angDiff = (a: number, b: number) => ((a - b + 540) % 360) - 180;

export type Profile = { az: number[]; el: number[] };
export function maskFor(site: Site, heightM: number): number[] {
  const out: number[] = [];
  const r1 = hash(site.id + 'a'), r2 = hash(site.id + 'b'), r3 = hash(site.id + 'c'), r4 = hash(site.id + 'd');
  const base = site.id === 'shackleton-floor' ? 3.4 : 0.15 + r1 * 0.6 - (site.height_m > 5000 ? 0.5 : 0);
  const rough = site.id === 'shackleton-floor' ? 1.2 : 0.4 + r2 * 0.9;
  for (let az = 0; az < 360; az++) {
    const a = az * rad;
    let v = base + rough * (Math.sin(3 * a + r3 * 6) * 0.9 + Math.sin(7 * a + r4 * 6) * 0.5 + Math.sin(13 * a + r1 * 9) * 0.3 + Math.sin(29 * a + r2 * 9) * 0.15);
    v += 0.45 + 0.4 * Math.sin(a - r3 * 6);
    v -= Math.log2(heightM / 2 + 1) * 0.42 * (site.id === 'shackleton-floor' ? 0.4 : 1);
    out.push(Math.max(-0.5, v));
  }
  return out;
}
export const maskAt = (m: number[], az: number) => {
  const x = wrap(az), i = Math.floor(x), f = x - i;
  return m[i % 360] * (1 - f) + m[(i + 1) % 360] * f;
};

export type Bodies = { sunAz: number; sunEl: number; earthAz: number; earthEl: number };
const SIDEREAL = 27.3217 * DAY;
export function bodiesAt(site: Site, t: number): Bodies {
  const ph = (t - Date.UTC(2000, 0, 6)) / SIDEREAL;
  const southness = Math.abs(site.lat);
  const amp = Math.max(0.2, 1.7 - (southness - 80) * 0.14) ;
  const yr = (t - Date.UTC(2000, 0, 1)) / (365.25 * DAY);
  const sunEl = 1.54 * Math.sin(2 * Math.PI * yr + 0.6) * (southness > 89 ? 1 : 0.9) + (90 - southness) * 0.0 + (southness > 89 ? 0 : 0.3 * Math.sin(2 * Math.PI * ph));
  const sunAz = wrap(360 * ph + site.lon);
  const l = (t - Date.UTC(2000, 0, 1)) / (27.5546 * DAY);
  const earthEl = 6.68 * Math.cos(rad * (site.lon)) * Math.sin(2 * Math.PI * l) * (amp / 1.7) + 2.2 - (southness - 85) * 0.35 * 0.3;
  const earthAz = wrap(site.lon * 0 + 8 * Math.sin(2 * Math.PI * (t - Date.UTC(2000, 0, 1)) / (27.2122 * DAY)) + (site.lon > 0 ? 6 : -6) + 360 - (site.lon / 4));
  return { sunAz, sunEl, earthAz, earthEl };
}

export const SUN_R = 0.267;
export const EARTH_R = 0.95;

export function sunFraction(mask: number[], b: Bodies): number {
  const m = maskAt(mask, b.sunAz);
  const x = (b.sunEl - m) / (SUN_R * 2);
  return Math.min(1, Math.max(0, x + 0.5));
}


const maskCache = new Map<string, number[]>();
export function cachedMask(site: Site, h: number) {
  const k = site.id + h; let m = maskCache.get(k);
  if (!m) { m = maskFor(site, h); maskCache.set(k, m); }
  return m;
}
export type Live = { sun: number; sunEl: number; sunClear: number; earthClear: number; earthUp: boolean; b: Bodies };
export function liveState(site: Site, t: number, h = 2): Live {
  const m = cachedMask(site, h), b = bodiesAt(site, t);
  const earthClear = b.earthEl - maskAt(m, b.earthAz);
  return { sun: sunFraction(m, b), sunEl: b.sunEl, sunClear: b.sunEl - maskAt(m, b.sunAz), earthClear, earthUp: earthClear > 0, b };
}

// Mission visibility and decisions come from the backend; this module only defines locations and display formatting.
const p2 = (n: number) => String(n).padStart(2, "0");
export const fmtDate = (ms: number) => {
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())}`;
};
export const fmtTime = (ms: number) => {
  const d = new Date(ms);
  return `${fmtDate(ms)} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())} UTC`;
};
export const fmtDur = (h: number) =>
  h >= 48
    ? `${h.toFixed(0)} h (${(h / 24).toFixed(1)} days)`
    : `${h.toFixed(1)} h`;
export const fmtLat = (v: number, d = 2) =>
  `${Math.abs(v).toFixed(d)}°${v < 0 ? "S" : "N"}`;
export const fmtLon = (v: number, d = 2) => {
  const n = ((((v + 180) % 360) + 360) % 360) - 180;
  return `${Math.abs(n).toFixed(d)}°${n < 0 ? "W" : "E"}`;
};
export const fmtPos = (s: Site, d = 2) =>
  `${fmtLat(s.lat, d)}, ${fmtLon(s.lon, d)}`;
