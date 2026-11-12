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
};
export type MissionRequest = {
  latitude_deg: number;
  longitude_e_deg: number;
  start_utc: string;
  duration_hours: number;
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
};
export type Validation = {
  passed: boolean;
  reason_codes?: string[];
  tolerance_status?: string;
  policy_version?: string;
};
export type Interval = {
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
  result_id: string;
  request: MissionRequest;
  decision: Decision | null;
  nominal_sampled_decision: Decision | null;
  metrics_hours: Record<string, Bounds>;
  constraint_checks: Record<string, Decision>;
  soft_constraint_checks: Record<string, Decision>;
  validation: Validation;
  timeline: Interval[];
  contact_analysis?: Contact;
  method_version: string;
  warnings: string[];
  coordinate: {
    latitude_deg: number;
    longitude_e_deg: number;
    observer_resolution_m: number;
    observer_dataset_id: string;
  };
};
export type Candidate = {
  candidate_id: string;
  site_id: string;
  start_utc: string;
  end_utc: string;
  decision: Decision;
  nominal_sampled_decision: Decision | null;
  metrics: Record<string, Bounds>;
  constraint_states: Record<string, Decision>;
  validation: Validation;
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
};
// Coordinates of the two documented requests, not precomputed science values.
export const EXAMPLES: Target[] = [
  {
    id: "example-a",
    name: "Example A",
    latitude: -88.80771296769387,
    longitude: 123.81313283430084,
    elevationM: NaN,
    status: "provisional",
  },
  {
    id: "example-b",
    name: "Example B",
    latitude: -87,
    longitude: 180,
    elevationM: NaN,
    status: "provisional",
  },
];
export function missionRequest(m: Mission, target: Target): MissionRequest {
  return {
    latitude_deg: target.latitude,
    longitude_e_deg: target.longitude,
    start_utc: new Date(m.start + "Z").toISOString(),
    duration_hours: m.hours,
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
  if (
    !Number.isFinite(stamp.valueOf()) ||
    stamp.getUTCFullYear() < 2000 ||
    stamp.getUTCFullYear() > 2100 ||
    stamp.getUTCMinutes() % 5 ||
    stamp.getUTCSeconds()
  )
    return "Use a UTC start in 2000–2100 on the 5-minute grid.";
  if (new Date(stamp.valueOf() + m.hours * 3600000).getUTCFullYear() > 2100)
    return "The mission must finish within 2100.";
  const limits: Array<[number, number, number, string]> = [
    [m.hours, 1, 72, "Mission duration"],
    [m.panel, 0.01, 20, "Panel height"],
    [m.antenna, 0.01, 20, "Antenna height"],
    [m.sun, 0, 100, "Minimum sunlight"],
    [m.contact, 0.01, 4320, "Contact duration"],
    [m.setup, 0, 4320, "Setup"],
    [m.windows, 1, 1000, "Required windows"],
    [m.deadline, 0, m.hours * 60, "First contact deadline"],
    [m.darkness, 0, 72, "Darkness preference"],
    [m.blackout, 0, 72, "Blackout preference"],
  ];
  for (const [v, lo, hi, name] of limits)
    if (!Number.isFinite(v) || v < lo || v > hi)
      return `${name} must be between ${lo} and ${hi}.`;
  if (!Number.isInteger(m.hours) || !Number.isInteger(m.windows))
    return "Mission hours and required windows must be whole numbers.";
  return null;
}
export const timestamp = (v: string) =>
  new Date(v).toISOString().replace("T", " ").replace(".000Z", " UTC");
export const boundsText = (pair?: Bounds) =>
  !pair
    ? "—"
    : Math.abs(pair[0] - pair[1]) < 1e-8
      ? `${Number(pair[0].toFixed(2))}`
      : `${Number(pair[0].toFixed(2))}–${Number(pair[1].toFixed(2))}`;
export function intervalAt(
  rows: Interval[],
  time: number,
): Interval | undefined {
  return rows.find(
    (r) => Date.parse(r.start_utc) <= time && time < Date.parse(r.end_utc),
  );
}
