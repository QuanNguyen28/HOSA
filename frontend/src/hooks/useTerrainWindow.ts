import { useEffect, useState } from "react";

import type {
  TerrainGeometryMetadata,
  TerrainGrid,
} from "../lib/terrainGeometry";
import type { LunarCoordinate } from "../types";

export type TerrainWindow = {
  coverage_status: "COVERED" | "UNKNOWN";
  dataset_id?: string;
  native_resolution_m?: number;
  detail?: "best" | "regional";
  radius_km?: number;
  geometry?: TerrainGeometryMetadata;
  grid: null | TerrainGrid;
  method_version: string;
  warnings: string[];
};

export function useTerrainWindow(
  coordinate: LunarCoordinate | null,
  enabled: boolean,
  options: {
    radiusKm?: number;
    samples?: 65 | 129 | 257 | 401 | 513;
    regionalOnly?: boolean;
  } = {},
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
      radius_km: (options.radiusKm ?? 8).toString(),
      samples: (options.samples ?? 257).toString(),
      detail: options.regionalOnly ? "regional" : "best",
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
  }, [coordinate, enabled, options.radiusKm, options.samples, options.regionalOnly]);

  return { result, loading };
}
