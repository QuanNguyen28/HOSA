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
];

export const HEIGHTS = [2, 10, 20];
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
