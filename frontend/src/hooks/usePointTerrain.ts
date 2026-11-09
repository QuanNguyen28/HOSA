import { useEffect, useMemo, useState } from "react";

import type { LunarCoordinate } from "../types";

export type PointTerrain = {
  coverage_status: "COVERED" | "UNKNOWN";
  terrain: null | {
    elevation_m: number;
    resolution_m: number;
    dataset_id: string;
    coverage_label: string;
    slope_deg: number | null;
    local_3x3_roughness_m: number | null;
    quality: null | {
      rms_error_m: number | null;
      lola_spot_count: number | null;
    };
  };
  method_version: string;
  warnings: string[];
};

export function usePointTerrain(
  coordinate: LunarCoordinate | null,
  enabled: boolean,
) {
  const key = useMemo(
    () => coordinate && `${coordinate.latitude.toFixed(7)},${coordinate.longitude.toFixed(7)}`,
    [coordinate],
  );
  const [result, setResult] = useState<PointTerrain | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!coordinate || !enabled || !key) {
      setResult(null);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      const query = new URLSearchParams({
        latitude: coordinate.latitude.toString(),
        longitude: coordinate.longitude.toString(),
      });
      fetch(`/api/lunar/point/terrain?${query}`, { signal: controller.signal })
        .then((response) => {
          if (!response.ok) throw new Error("Terrain query unavailable");
          return response.json();
        })
        .then(setResult)
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setResult(null);
        })
        .finally(() => setLoading(false));
    }, 180);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [coordinate, enabled, key]);

  return { result, loading };
}
