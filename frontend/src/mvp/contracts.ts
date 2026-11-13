import compareSites from "../../../manifests/compare-sites.json";

export type Decision = "PASS" | "FAIL" | "INDETERMINATE";
export type Bounds = [number, number];
export type Target = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  elevationM: number;
  status: "verified" | "provisional";
};
export type Mission = {
  start: string;
  timing: "hours" | "end";
  end: string;
  hours: number;
  panel: number;
  antenna: number;
  sun: number;
  contact: number;
  setup: number;
  windows: number;
  deadline: number;
  darkness: number;
  blackout: number;
  offline: boolean;
  resolve_indeterminate: boolean;
};
export type MissionRequest = {
  illumination_model: "solar_disc";
  latitude_deg: number;
  longitude_e_deg: number;
  start_utc: string;
  duration_hours: number;
  end_utc: string;
  panel_height_m: number;
  antenna_height_m: number;
  min_sunlit_fraction: number;
  contact_requirements: {
    min_contact_minutes: number;
    setup_minutes: number;
    required_windows: number;
    first_contact_deadline_minutes: number;
  };
  constraints: { max_darkness_hours: number; max_earth_blackout_hours: number };
  offline: boolean;
  resolve_indeterminate: boolean;
};
export type Resolution = {
  enabled?: boolean;
  status?: string;
  refinement_rounds?: number;
  initial_decision?: Decision | null;
  final_decision?: Decision | null;
  initial_reason_codes?: string[];
  remaining_reason_codes?: string[];
  error_code?: string;
};
export type Validation = {
  status?: string;
  passed: boolean;
  mission_path?: {
    passed: boolean;
    scope?: string;
    reason?: string;
    metrics_hours?: Record<string, Bounds>;
  };
  reason_codes?: string[];
  tolerance_status?: string;
  policy_version?: string;
};
export type Interval = {
  evidence_source?: "prepared_nominal";
  sampling_minutes?: number;
  aggregated?: boolean;
  earth_visible_fraction_lower?: number;
  earth_visible_fraction_upper?: number;
  joint_visible_fraction_lower?: number;
  joint_visible_fraction_upper?: number;
  sun_visible_fraction?: number | null;
  sun_visible_fraction_lower?: number;
  sun_visible_fraction_upper?: number;
  start_utc: string;
  end_utc: string;
  sun_state: "V" | "B" | "?";
  earth_state: "V" | "B" | "?";
  joint_state: "V" | "B" | "?";
  sun_az_deg?: number | null;
  sun_el_deg?: number | null;
  earth_az_deg?: number | null;
  earth_el_deg?: number | null;
  sun_horizon_deg?: number | null;
  earth_horizon_deg?: number | null;
  sun_clearance_deg?: number | null;
  earth_clearance_deg?: number | null;
};
// Duration-weighted display bins bound the DOM for multi-year missions.
// Unknown evidence stays hatched; aggregation never affects engine decisions.
export function timelineBins(rows: Interval[], start: number, end: number, columns = 800): Interval[] {
  if (!rows.length || !(end > start)) return [];
  // Backend bins may have different widths. Re-splitting their averages would
  // invent detail inside a bin and smear transitions into neighbouring bins.
  if (rows.length <= columns && rows.every((row, i) => row.aggregated &&
      Date.parse(row.start_utc) === (i ? Date.parse(rows[i-1].end_utc) : start)) &&
      Date.parse(rows.at(-1)!.end_utc) === end) return rows;
  const count = Math.max(1, Math.min(columns, rows.length));
  const width = (end - start) / count;
  const bins: Interval[] = [];
  let cursor = 0;
  for (let j = 0; j < count; j++) {
    const a = start + j * width, b = start + (j + 1) * width;
    const totals = { sun: [0, 0], earth: [0, 0], joint: [0, 0] };
    let covered = 0;
    while (cursor < rows.length && Date.parse(rows[cursor].end_utc) <= a) cursor++;
    for (let i = cursor; i < rows.length && Date.parse(rows[i].start_utc) < b; i++) {
      const row = rows[i];
      const dt = Math.max(0, Math.min(b, Date.parse(row.end_utc)) - Math.max(a, Date.parse(row.start_utc)));
      covered += dt;
      for (const body of ["sun", "earth", "joint"] as const) {
        const state = row[`${body}_state`];
        const lo = row[`${body}_visible_fraction_lower`] ?? (body === "sun" ? row.sun_visible_fraction : undefined) ?? (state === "V" ? 1 : 0);
        const hi = row[`${body}_visible_fraction_upper`] ?? (body === "sun" ? row.sun_visible_fraction : undefined) ?? (state === "B" ? 0 : 1);
        totals[body][0] += lo * dt;
        totals[body][1] += hi * dt;
      }
    }
    const state = (body: "sun" | "earth" | "joint"): Interval["sun_state"] => {
      const [lo, hi] = totals[body];
      if (covered < width - 1 || hi - lo > 1 || (body !== "sun" && lo > 0 && hi < width - 1)) return "?";
      return hi > 0 ? "V" : "B";
    };
    bins.push({ start_utc: new Date(a).toISOString(), end_utc: new Date(b).toISOString(),
      aggregated: true,
      sun_state: state("sun"), earth_state: state("earth"), joint_state: state("joint"),
      sun_visible_fraction: state("sun") !== "?" ? totals.sun[0] / width : null,
      sun_visible_fraction_lower: totals.sun[0] / width,
      sun_visible_fraction_upper: (totals.sun[1] + Math.max(0, width - covered)) / width,
      earth_visible_fraction_lower: totals.earth[0] / width,
      earth_visible_fraction_upper: (totals.earth[1] + Math.max(0, width - covered)) / width,
      joint_visible_fraction_lower: totals.joint[0] / width,
      joint_visible_fraction_upper: (totals.joint[1] + Math.max(0, width - covered)) / width });
  }
  return bins;
}
export type Contact = {
  visible_windows: Array<{
    start_utc: string;
    end_utc: string;
    duration_minutes: number;
    usable_duration_minutes: number;
    qualifies: boolean;
  }>;
  metrics: { qualified_windows_count: number; visible_windows_count: number };
};
export type PointResult = {
  evaluation_stages?: Record<string, string>;
  hard_failure?: {
    constraint: string;
    limit: number | Record<string, unknown>;
    observed_bounds?: Bounds;
    shortfall_hours_bounds?: Bounds;
    window: { start_utc: string; end_utc: string };
    coordinate: { latitude_deg: number; longitude_e_deg: number };
    explanation: string;
    sampling_minutes?: number;
    confirmed_sampling_minutes?: number[];
    deadline_utc?: string;
    evidence_intervals: Array<{ target: string; start_utc: string; end_utc: string; at_utc?: string }>;
  } | null;
  joint_hours?: Bounds;
  evaluation_status?: "pending" | "complete";
  timeline_transport?: { mode: "native" | "aggregated" | "pending"; source_intervals: number; display_intervals: number; exact_intervals_ready?: boolean };
  interval_url?: string;
  instant?: Interval;
  illumination?: { model: string; mean_visible_fraction_bounds: Bounds };
  result_id: string;
  request: MissionRequest;
  decision: Decision | null;
  nominal_sampled_decision: Decision | null;
  metrics_hours: Record<string, Bounds>;
  constraint_checks: Record<string, Decision>;
  soft_constraint_checks: Record<string, Decision>;
  validation: Validation;
  resolution?: Resolution;
  timeline: Interval[];
  contact_analysis?: Contact;
  method_version: string;
  warnings: string[];
  coordinate: {
    dem_elevation_m?: number;
    latitude_deg: number;
    longitude_e_deg: number;
    observer_resolution_m: number;
    observer_dataset_id: string;
  };
};
export type Candidate = {
  evaluation_stages?: Record<string, string>;
  hard_failure?: PointResult["hard_failure"];
  candidate_id: string;
  site_id: string;
  start_utc: string;
  end_utc: string;
  decision: Decision;
  nominal_sampled_decision: Decision | null;
  metrics: Record<string, Bounds>;
  constraint_states: Record<string, Decision>;
  validation: Validation;
  resolution?: Resolution;
  coordinate?: { latitude_deg: number; longitude_e_deg: number };
  analysis_result_id?: string;
};
export type PlanningResult = {
  result_id: string;
  operation: string;
  status: string;
  candidates: Candidate[];
  recommended_candidate_id: string | null;
  apply_allowed: boolean;
  coverage: Record<string, number>;
  method_version: string;
  warnings: string[];
};
export const DEFAULT_MISSION: Mission = {
  start: "2026-11-24T00:00",
  timing: "hours",
  end: "2026-11-27T00:00",
  hours: 72,
  panel: 20,
  antenna: 20,
  sun: 80,
  contact: 30,
  setup: 5,
  windows: 1,
  deadline: 120,
  darkness: 12,
  blackout: 6,
  offline: false,
  resolve_indeterminate: true,
};
export function missionHours(m: Mission): number {
  return m.timing === "end"
    ? (Date.parse(m.end + "Z") - Date.parse(m.start + "Z")) / 3600000
    : m.hours;
}
export function missionEnd(m: Mission): string {
  const end = Date.parse(m.start + "Z") + missionHours(m) * 3600000;
  const date = new Date(end);
  return Number.isFinite(date.valueOf()) ? date.toISOString().slice(0, 16) : "";
}
// Coordinates of the two documented requests, not precomputed science values.
export const EXAMPLES: Target[] = compareSites
  .filter((site) => site.id.startsWith("example-"))
  .map((site) => ({
    id: site.id,
    name: site.name,
    latitude: site.lat,
    longitude: site.lon,
    elevationM: NaN,
    status: "provisional",
  }));
export function missionRequest(m: Mission, target: Target): MissionRequest {
  return {
    illumination_model: "solar_disc",
    latitude_deg: target.latitude,
    longitude_e_deg: target.longitude,
    start_utc: new Date(m.start + "Z").toISOString(),
    duration_hours: missionHours(m),
    end_utc: new Date(missionEnd(m) + "Z").toISOString(),
    panel_height_m: m.panel,
    antenna_height_m: m.antenna,
    min_sunlit_fraction: m.sun / 100,
    contact_requirements: {
      min_contact_minutes: m.contact,
      setup_minutes: m.setup,
      required_windows: m.windows,
      first_contact_deadline_minutes: m.deadline,
    },
    constraints: {
      max_darkness_hours: m.darkness,
      max_earth_blackout_hours: m.blackout,
    },
    offline: m.offline,
    resolve_indeterminate: m.resolve_indeterminate,
  };
}
export function planningRequest(m: Mission, targets: Target[]) {
  const {
    latitude_deg: _lat,
    longitude_e_deg: _lon,
    start_utc,
    panel_height_m,
    antenna_height_m,
    ...rest
  } = missionRequest(m, targets[0]);
  return {
    ...rest,
    data_source: "coordinate",
    targets: targets.map((t) => ({
      latitude_deg: t.latitude,
      longitude_e_deg: t.longitude,
    })),
    arrival_utc: start_utc,
    hardware: { sun_panel: panel_height_m, earth_antenna: antenna_height_m },
    rank_by: "total_sun_hours",
  };
}
export function missionIssue(m: Mission): string | null {
  const stamp = new Date(m.start + "Z");
  const hours = missionHours(m);
  if (
    !Number.isFinite(stamp.valueOf()) ||
    stamp.getUTCMinutes() % 5 ||
    stamp.getUTCSeconds()
  )
    return "Use a valid UTC start on the 5-minute grid.";
  const end = new Date(stamp.valueOf() + hours * 3600000);
  if (!Number.isFinite(end.valueOf()))
    return "Choose a valid mission end date.";
  const limits: Array<[number, number, number, string]> = [
    [hours, 1, Infinity, "Mission duration"],
    [m.panel, 0.01, 30, "Panel height"],
    [m.antenna, 0.01, 30, "Antenna height"],
    [m.sun, 0, 100, "Minimum sunlight"],
    [m.contact, 0.01, hours * 60, "Contact duration"],
    [m.setup, 0, hours * 60, "Setup"],
    [m.windows, 1, 1000, "Required windows"],
    [m.deadline, 0, hours * 60, "First contact deadline"],
    [m.darkness, 0, Infinity, "Darkness preference"],
    [m.blackout, 0, Infinity, "Blackout preference"],
  ];
  for (const [v, lo, hi, name] of limits)
    if (!Number.isFinite(v) || v < lo || v > hi)
      return Number.isFinite(hi)
        ? `${name} must be between ${lo} and ${hi}.`
        : `${name} must be a finite number of at least ${lo}.`;
  if (Math.abs(hours * 12 - Math.round(hours * 12)) > 1e-7)
    return "Use a mission duration or end date on the 5-minute grid.";
  if (!Number.isInteger(m.windows))
    return "Required windows must be a whole number.";
  return null;
}
export const timestamp = (v: string) =>
  new Date(v).toISOString().replace("T", " ").replace(".000Z", " UTC");
export function boundsText(pair?: Bounds, digits = 2): string {
  if (!pair) return "—";
  const [lower, upper] = pair.map((value) => `${Number(value.toFixed(digits))}`);
  return lower === upper ? lower : `${lower}–${upper}`;
}
export function intervalAt(
  rows: Interval[],
  time: number,
): Interval | undefined {
  // Do not treat a display average across days as an exact current state.
  let low = 0, high = rows.length;
  while (low < high) {
    const mid = (low + high) >>> 1;
    if (Date.parse(rows[mid].start_utc) <= time) low = mid + 1;
    else high = mid;
  }
  const row = rows[low - 1];
  return row && !row.aggregated && time < Date.parse(row.end_utc) ? row : undefined;
}

export function currentInterval(result: PointResult, time: number): Interval | undefined {
  return (result.instant && intervalAt([result.instant], time)) ?? intervalAt(result.timeline, time);
}
