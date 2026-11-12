import { useEffect, useState } from "react";

export type SouthPolarFootprint = {
  site_id: string;
  dataset_id: string;
  native_resolution_m: number;
  bounds_xy_m: [number, number, number, number];
  ring_lon_lat: Array<[number, number]>;
};

export type SouthPolarTerrain = {
  coverage_status: "COVERED";
  dataset_id: string;
  native_resolution_m: number;
  latitude_limit_deg: number;
  projection: {
    name: string;
    lunar_reference_radius_m: number;
    bounds_xy_m: [number, number, number, number];
  };
  grid: {
    rows: number;
    columns: number;
    elevation_m_row_major: Array<number | null>;
    min_elevation_m: number;
    max_elevation_m: number;
    valid_fraction: number;
    effective_spacing_m: number;
  };
  site_footprints: SouthPolarFootprint[];
  method_version: string;
  warnings: string[];
};

let cached: SouthPolarTerrain | null = null;
let pending: Promise<SouthPolarTerrain> | null = null;

function loadCap() {
  if (cached) return Promise.resolve(cached);
  if (!pending) {
    pending = fetch("/api/lunar/terrain/south-polar-cap?samples=513")
      .then((response) => {
        if (!response.ok) throw new Error("South-polar terrain unavailable");
        return response.json() as Promise<SouthPolarTerrain>;
      })
      .then((result) => {
        cached = result;
        return result;
      })
      .finally(() => {
        pending = null;
      });
  }
  return pending;
}

export function useSouthPolarTerrain(enabled: boolean) {
  const [result, setResult] = useState<SouthPolarTerrain | null>(cached);
  const [loading, setLoading] = useState(enabled && cached === null);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setLoading(cached === null);
    loadCap()
      .then((value) => {
        if (active) setResult(value);
      })
      .catch(() => {
        if (active) setResult(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  return { result, loading };
}
