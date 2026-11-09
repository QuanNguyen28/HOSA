import { useEffect, useMemo, useState } from "react";

type BodyState = {
  state: "V" | "B" | "?";
  azimuth_deg: number | null;
  elevation_deg: number | null;
  horizon_deg: number | null;
  clearance_deg: number | null;
  coverage: string;
};

export type SiteAnalysis = {
  site_id: string;
  at_utc: string;
  availability: "AVAILABLE" | "OUTSIDE_EPHEMERIS_RANGE";
  scenario_status?: string;
  instant?: {
    start_utc: string;
    end_utc: string;
    sun: BodyState;
    earth: BodyState;
    joint_state: "V" | "B" | "?";
  };
  window_72h?: {
    start_utc: string;
    end_utc: string;
    decision: "PASS" | "FAIL" | "INDETERMINATE";
    darkness_constraint: string;
    earth_constraint: string;
    total_sun_hours: [number, number];
    longest_dark_hours: [number, number];
    longest_blackout_hours: [number, number];
    longest_joint_hours: [number, number];
  } | null;
  dataset_version: string;
  method_version: string;
  provenance?: {
    visibility: string;
    windows: string;
  };
  warnings: string[];
};

export function useSiteAnalysis(siteId: string | null, time: Date) {
  const queryTime = useMemo(() => {
    const value = new Date(time);
    const isExactStart = value.getUTCMinutes() % 15 === 0 && value.getUTCSeconds() === 0 && value.getUTCMilliseconds() === 0;
    if (!isExactStart) {
      value.setUTCSeconds(0, 1);
      value.setUTCMinutes(Math.floor(value.getUTCMinutes() / 5) * 5);
    }
    return value.toISOString();
  }, [time]);
  const [analysis, setAnalysis] = useState<SiteAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!siteId) {
      setAnalysis(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    fetch(
      `/api/lunar/sites/${encodeURIComponent(siteId)}/analysis?at_utc=${encodeURIComponent(queryTime)}`,
      { signal: controller.signal },
    )
      .then((response) => {
        if (!response.ok) throw new Error("Analysis unavailable");
        return response.json();
      })
      .then(setAnalysis)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setAnalysis(null);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [queryTime, siteId]);

  return { analysis, loading };
}
