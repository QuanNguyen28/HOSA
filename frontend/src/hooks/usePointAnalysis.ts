import { useEffect, useMemo, useState } from "react";

import type { LunarCoordinate } from "../types";

export type PointAnalysisResult = {
  result_id: string;
  decision: "PASS" | "FAIL" | "INDETERMINATE" | null;
  nominal_sampled_decision: "PASS" | "FAIL" | "INDETERMINATE" | null;
  coordinate: {
    latitude_deg: number;
    longitude_e_deg: number;
    dem_elevation_m: number;
    observer_dataset_id: string;
    observer_resolution_m: number;
  };
  availability_fraction: {
    sun: [number, number];
    earth: [number, number];
  };
  metrics_hours: Record<string, [number, number]>;
  coverage: {
    terrain_complete: boolean;
    ephemeris_complete: boolean;
    covered_azimuth_fraction_by_height: Record<string, number>;
  };
  validation: { passed?: boolean } & Record<string, unknown>;
  timeline: Array<{
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
  }>;
  events: Array<{
    target: "sun" | "earth" | "joint";
    state: "V" | "B" | "?";
    start_utc: string;
    end_utc: string;
  }>;
  warnings: string[];
};

type AnalysisState = {
  status: "idle" | "queued" | "running" | "succeeded" | "failed";
  stage: string;
  result: PointAnalysisResult | null;
  errorCode: string | null;
};

const completed = new Map<string, PointAnalysisResult>();
const running = new Map<string, Promise<PointAnalysisResult>>();

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function runAnalysis(payload: Record<string, unknown>) {
  const submitted = await fetch("/api/lunar/point/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!submitted.ok) {
    const body = await submitted.json().catch(() => null);
    throw new Error(body?.detail?.code ?? "POINT_ANALYSIS_UNAVAILABLE");
  }
  const job = await submitted.json() as { job_id: string };
  for (let attempt = 0; attempt < 600; attempt += 1) {
    await delay(attempt < 5 ? 900 : 1_800);
    const response = await fetch(`/api/lunar/point/analyses/${job.job_id}`);
    if (!response.ok) throw new Error("POINT_JOB_UNAVAILABLE");
    const status = await response.json() as {
      status: "queued" | "running" | "succeeded" | "failed";
      error_code?: string | null;
      result_url?: string | null;
    };
    if (status.status === "failed") {
      throw new Error(status.error_code ?? "POINT_ANALYSIS_FAILED");
    }
    if (status.status === "succeeded" && status.result_url) {
      const result = await fetch(status.result_url);
      if (!result.ok) throw new Error("POINT_RESULT_UNAVAILABLE");
      return result.json() as Promise<PointAnalysisResult>;
    }
  }
  throw new Error("POINT_ANALYSIS_TIMEOUT");
}

function fiveMinuteUtc(timeMs: number) {
  const rounded = Math.floor(timeMs / 300_000) * 300_000;
  return new Date(rounded).toISOString().replace(".000Z", "Z");
}

export function usePointAnalysis(
  coordinate: LunarCoordinate | null,
  timeMs: number,
  observerHeightM: number,
  enabled: boolean,
) {
  const payload = useMemo(() => coordinate ? {
    latitude_deg: coordinate.latitude,
    longitude_e_deg: coordinate.longitude,
    start_utc: fiveMinuteUtc(timeMs),
    duration_hours: 72,
    panel_height_m: observerHeightM,
    antenna_height_m: observerHeightM,
    min_sunlit_fraction: 0.8,
    min_earth_los_fraction: 0.8,
    offline: false,
  } : null, [coordinate, observerHeightM, timeMs]);
  const key = useMemo(() => payload ? JSON.stringify(payload) : "", [payload]);
  const [state, setState] = useState<AnalysisState>({
    status: "idle",
    stage: "idle",
    result: null,
    errorCode: null,
  });

  useEffect(() => {
    if (!enabled || !payload || !key) {
      setState({ status: "idle", stage: "idle", result: null, errorCode: null });
      return;
    }
    let active = true;
    const cached = completed.get(key);
    if (cached) {
      setState({ status: "succeeded", stage: "complete", result: cached, errorCode: null });
      return;
    }
    setState({ status: "queued", stage: "terrain and ephemeris", result: null, errorCode: null });
    const timer = window.setTimeout(() => {
      if (!active) return;
      setState((current) => ({ ...current, status: "running", stage: "terrain horizon" }));
      let task = running.get(key);
      if (!task) {
        task = runAnalysis(payload);
        running.set(key, task);
      }
      task
        .then((result) => {
          completed.set(key, result);
          if (active) setState({ status: "succeeded", stage: "complete", result, errorCode: null });
        })
        .catch((error: unknown) => {
          if (active) setState({
            status: "failed",
            stage: "failed",
            result: null,
            errorCode: error instanceof Error ? error.message : "POINT_ANALYSIS_FAILED",
          });
        })
        .finally(() => running.delete(key));
    }, 500);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [enabled, key, payload]);

  return state;
}
