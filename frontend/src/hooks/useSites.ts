import { useEffect, useState } from "react";

import { FALLBACK_SITES } from "../data/sites";
import type { Site } from "../types";

type CatalogFeature = {
  id?: string;
  geometry: { coordinates: [number, number] };
  properties: {
    site_id?: string;
    region?: string;
    dem_z_m?: number;
  };
};

export function useSites(): { sites: Site[]; source: "api" | "snapshot" } {
  const [sites, setSites] = useState(FALLBACK_SITES);
  const [source, setSource] = useState<"api" | "snapshot">("snapshot");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/lunar/sites", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Catalog unavailable");
        return response.json();
      })
      .then((catalog: { features?: CatalogFeature[] }) => {
        if (!catalog.features?.length) return;
        setSites(
          catalog.features.map((feature) => ({
            id: feature.properties.site_id ?? feature.id ?? "Unknown site",
            name: feature.properties.region ?? "Lunar candidate site",
            longitude: feature.geometry.coordinates[0],
            latitude: feature.geometry.coordinates[1],
            elevationM: feature.properties.dem_z_m ?? Number.NaN,
            status: "verified",
          })),
        );
        setSource("api");
      })
      .catch(() => undefined);

    return () => controller.abort();
  }, []);

  return { sites, source };
}
