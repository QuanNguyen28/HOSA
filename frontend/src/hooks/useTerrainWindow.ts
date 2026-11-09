import { useEffect, useState } from "react";

import type { LunarCoordinate } from "../types";

export type TerrainWindow = {
  coverage_status: "COVERED" | "UNKNOWN";
  dataset_id?: string;
  native_resolution_m?: number;
  radius_km?: number;
  grid: null | {
    rows: number;
    columns: number;
    elevation_m_row_major: Array<number | null>;
    min_elevation_m: number;
    max_elevation_m: number;
    valid_fraction: number;
    spacing_m: number;
  };
  method_version: string;
  warnings: string[];
};

export function useTerrainWindow(
  coordinate: LunarCoordinate | null,
  enabled: boolean,
) {
  const [result, setResult] = useState<TerrainWindow | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!coordinate || !enabled) {
      setResult(null);
      return;
    }
    const controller = new AbortController();
    const query = new URLSearchParams({
      latitude: coordinate.latitude.toString(),
      longitude: coordinate.longitude.toString(),
      radius_km: "8",
      samples: "129",
    });
    setLoading(true);
    fetch(`/api/lunar/point/terrain-window?${query}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Terrain window unavailable");
        return response.json();
      })
      .then(setResult)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setResult(null);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [coordinate, enabled]);

  return { result, loading };
}
