import { useMemo, useState } from "react";

import { MoonScene } from "../components/MoonScene";
import { useTerrainWindow } from "../hooks/useTerrainWindow";
import type {
  CameraPreset,
  LayerState,
  LunarCoordinate,
  Site as RendererSite,
} from "../types";
import { type Site } from "./model";

export type Mode = "orbit" | "pole" | "surface";

type Props = {
  mode: Mode;
  sites: Site[];
  onCoordinateSelect?: (coordinate: LunarCoordinate) => void;
  siteId: string;
  timeMs: number;
  heightM?: number;
  onSelect?: (id: string) => void;
  className?: string;
  interactive?: boolean;
};

const LAYERS: LayerState = {
  labels: true,
  grid: false,
  sites: true,
  enhancedLight: true,
};

function toRendererSite(site: Site): RendererSite {
  return {
    id: site.id,
    name: site.name,
    latitude: site.lat,
    longitude: site.lon,
    elevationM: site.height_m,
    status: site.kind === "exact" ? "verified" : "provisional",
  };
}

function modeToPreset(mode: Mode): CameraPreset {
  if (mode === "pole") return "south-pole";
  if (mode === "surface") return "surface";
  return "orbit";
}

export default function Stage3D({
  mode,
  sites: catalog,
  onCoordinateSelect,
  siteId,
  timeMs,
  onSelect,
  className = "",
  interactive = true,
}: Props) {
  const sites = useMemo(() => catalog.map(toRendererSite), [catalog]);
  const activeSite = useMemo(
    () => sites.find((site) => site.id === siteId) ?? sites[0],
    [siteId, sites],
  );
  const selected = activeSite;
  const selectedSiteId = activeSite.id === "custom" ? null : activeSite.id;
  const [hovered, setHovered] = useState<LunarCoordinate | null>(null);
  const [ready, setReady] = useState(false);
  const hasFiveMetreDem =
    selectedSiteId === "Site01_P1" || selectedSiteId === "Site04_P1";
  const { result: terrainWindow, loading: terrainLoading } = useTerrainWindow(
    selected,
    mode === "surface",
    hasFiveMetreDem
      ? { radiusKm: 2, samples: 513 }
      : { radiusKm: 8, samples: 257 },
  );

  const handleSelect = (
    coordinate: LunarCoordinate,
    rendererSiteId?: string,
  ) => {
    if (!rendererSiteId) onCoordinateSelect?.(coordinate);
    if (rendererSiteId) {
      onSelect?.(rendererSiteId);
    }
  };

  return (
    <div
      className={`overflow-hidden bg-black ${className}`}
      style={{ pointerEvents: interactive ? "auto" : "none" }}
    >
      <div className="relative h-full w-full">
        <MoonScene
          key={mode === "surface" ? "terrain" : "globe"}
          time={new Date(timeMs)}
          cameraPreset={modeToPreset(mode)}
          layers={LAYERS}
          sites={sites}
          selected={selected}
          selectedSiteId={selectedSiteId}
          terrainWindow={terrainWindow}
          onSelect={handleSelect}
          onHover={setHovered}
          onReady={() => setReady(true)}
        />
      </div>

      {!ready && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-black font-mono text-[11px] tracking-widest text-mute">
          LOADING NASA LUNAR SURFACE…
        </div>
      )}

      {mode === "surface" && terrainLoading && (
        <div className="pointer-events-none absolute top-16 left-1/2 -translate-x-1/2 border border-line bg-black/80 px-3 py-1.5 font-mono text-[10px] tracking-wider text-soft">
          PREPARING LOLA TERRAIN…
        </div>
      )}

      {mode === "surface" && terrainWindow?.grid && (
        <div className="pointer-events-none absolute top-16 left-4 border border-line bg-black/80 px-3 py-2 font-mono text-[10px] leading-relaxed tracking-wider text-soft">
          <div className="text-mint">LOLA TERRAIN · TRUE SCALE 1×</div>
          <div className="text-mute">
            {terrainWindow.dataset_id} · source{" "}
            {terrainWindow.native_resolution_m} m
          </div>
          <div className="text-mute">
            mesh {terrainWindow.grid.spacing_m.toFixed(1)} m ·{" "}
            {terrainWindow.grid.rows}² vertices
          </div>
          <div className="text-mute">
            {(terrainWindow.radius_km! * 2).toFixed(0)} km field · curvature
            enabled
          </div>
        </div>
      )}

      {hovered && mode !== "surface" && (
        <div className="pointer-events-none absolute right-4 bottom-4 border border-line bg-black/75 px-2.5 py-1.5 font-mono text-[10px] text-soft tabular">
          {Math.abs(hovered.latitude).toFixed(4)}°
          {hovered.latitude < 0 ? "S" : "N"} ·{" "}
          {Math.abs(hovered.longitude).toFixed(4)}°
          {hovered.longitude < 0 ? "W" : "E"}
        </div>
      )}
    </div>
  );
}
