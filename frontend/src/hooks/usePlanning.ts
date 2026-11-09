import { useCallback, useEffect, useState } from "react";

export type Scenario = {
  scenario_id: string;
  status: string;
  A_utc: string;
  B_utc: string;
  end_utc: string;
  D_hours: number;
  model_step_minutes: number;
  start_step_minutes: number;
  start_count: number;
  site_ids: string[];
  device_heights_m: { sun_panel: number; earth_antenna: number };
  example_constraints: {
    max_darkness_hours: number;
    max_earth_blackout_hours: number;
  };
};

export type PlanningEvent = {
  body: "sun" | "earth";
  state: "B" | "?";
  start_utc: string;
  end_utc: string;
  duration_hours: number;
  worst_sample: {
    at_utc: string;
    azimuth_deg: number | null;
    elevation_deg: number | null;
    horizon_deg: number | null;
    clearance_deg: number | null;
    coverage_flag: string;
  };
};

export type SitePlan = {
  site_id: string;
  scenario_status: string;
  start_index: number;
  start_utc: string;
  end_utc: string;
  metrics: Record<string, [number, number]>;
  constraint_states: {
    max_darkness_hours: "PASS" | "FAIL" | "INDETERMINATE";
    max_earth_blackout_hours: "PASS" | "FAIL" | "INDETERMINATE";
  };
  decision: "PASS" | "FAIL" | "INDETERMINATE";
  decisive_event: PlanningEvent | null;
  events: PlanningEvent[];
  sensitivity: {
    status: "STABLE_DECISION" | "REVIEW" | "NOT_EVALUATED";
    angular_sensitive?: boolean;
    time_sensitive?: boolean;
    azimuth_decisions_changed?: number;
    max_horizon_difference_deg?: number;
    max_duration_difference_minutes?: number;
    max_event_shift_minutes?: number;
    source: string;
  };
};

export type PlanningResult = {
  result_id: string;
  request: {
    scenario_id: string;
    site_ids: string[];
    start_index: number;
    constraints: {
      max_darkness_hours: number;
      max_earth_blackout_hours: number;
    };
  };
  sites: SitePlan[];
  overall_decision: "PASS" | "FAIL" | "INDETERMINATE";
  dataset_version: string;
  method_version: string;
  warnings: string[];
};

export type HorizonProfile = {
  site_id: string;
  target: "sun" | "earth";
  observer_height_m: number;
  azimuth_step_deg: number;
  coverage_complete: boolean;
  points: Array<{
    azimuth_deg: number;
    horizon_deg: number;
    blocker_distance_m: number;
    blocker_source: string;
    coverage_complete: boolean;
  }>;
};

export function usePlanning() {
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [result, setResult] = useState<PlanningResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/scenarios")
      .then(async (response) => {
        if (!response.ok) throw new Error(`Scenario API returned ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (!cancelled) setScenario(payload.scenarios[0] ?? null);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Unable to load scenario");
      });
    return () => { cancelled = true; };
  }, []);

  const analyze = useCallback(async (
    startIndex: number,
    maxDarknessHours: number,
    maxBlackoutHours: number,
  ) => {
    if (!scenario) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: scenario.scenario_id,
          site_ids: scenario.site_ids,
          start_index: startIndex,
          constraints: {
            max_darkness_hours: maxDarknessHours,
            max_earth_blackout_hours: maxBlackoutHours,
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? `Analysis API returned ${response.status}`);
      setResult(payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, [scenario]);

  return { scenario, result, loading, error, analyze };
}

export function useHorizonProfile(siteId: string, target: "sun" | "earth") {
  const [profile, setProfile] = useState<HorizonProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProfile(null);
    setError(null);
    fetch(`/api/sites/${encodeURIComponent(siteId)}/profile?target=${target}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Profile API returned ${response.status}`);
        return response.json();
      })
      .then((payload) => { if (!cancelled) setProfile(payload); })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Profile unavailable");
      });
    return () => { cancelled = true; };
  }, [siteId, target]);

  return { profile, error };
}

