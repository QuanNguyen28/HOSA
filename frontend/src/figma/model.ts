import compareSites from "../../../manifests/compare-sites.json";

export type Site = {
  id: string;
  name: string;
  group: "nasa" | "illumination" | "artemis" | "clps" | "contrast";
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
  nasa: "NASA south-pole regions",
  illumination: "High-illumination points",
  artemis: "Artemis candidate regions",
  clps: "CLPS landing sites",
  contrast: "Permanent shadow",
};
export const GROUP_ORDER: Site["group"][] = [
  "nasa",
  "illumination",
  "artemis",
  "clps",
  "contrast",
];

export const SITES = compareSites
  .filter((site) => !("default_visible" in site) || site.default_visible !== false)
  .map((site) => ({ ...site, height_m: site.height_m ?? NaN })) as Site[];

export const HIDDEN_DEFAULT_SITE_IDS = new Set(["Site01_P1", "Site04_P1", "example-a", "example-b"]);

export const HEIGHTS = [2, 10, 20, 30];
export const SPEEDS = [1, 6, 24, 72];
export const speedLabel = (h: number) =>
  h >= 24
    ? `${h / 24} day${h > 24 ? "s" : ""} per second`
    : `${h} hour${h > 1 ? "s" : ""} per second`;

export const HOUR = 3600e3;
export const DAY = 24 * HOUR;
// Viewer seeks must represent refined one-minute evidence. Mission inputs
// independently retain the backend's five-minute boundary requirement.
export const STEP = 60e3;
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
