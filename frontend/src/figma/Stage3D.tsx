import { useEffect, useMemo, useState } from "react";

import { MoonScene } from "../components/MoonScene";
import { useTerrainWindow } from "../hooks/useTerrainWindow";
import type {
  CameraPreset,
  LayerState,
  LunarCoordinate,
  Site as RendererSite,
} from "../types";
import { SITES } from "./model";

export type Mode = "orbit" | "pole" | "surface";

type Props = {
  mode: Mode;
  siteId: string;
  timeMs: number;
  heightM?: number;
  onSelect?: (id: string) => void;
  className?: string;
  interactive?: boolean;
};

const TEMPLATE_TO_RENDERER_ID: Record<string, string> = {
  "connecting-ridge": "Site01_P1",
  "shackleton-rim": "Site04_P1",
};

const RENDERER_TO_TEMPLATE_ID = Object.fromEntries(
  Object.entries(TEMPLATE_TO_RENDERER_ID).map(([templateId, rendererId]) => [rendererId, templateId]),
);

const LAYERS: LayerState = {
  labels: true,
  grid: false,
  sites: true,
  enhancedLight: true,
};

function toRendererSite(site: (typeof SITES)[number]): RendererSite {
  return {
    id: TEMPLATE_TO_RENDERER_ID[site.id] ?? site.id,
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
  siteId,
  timeMs,
  onSelect,
  className = "",
  interactive = true,
}: Props) {
  const sites = useMemo(() => SITES.map(toRendererSite), []);
  const activeSite = useMemo(
    () => sites.find((site) => site.id === (TEMPLATE_TO_RENDERER_ID[siteId] ?? siteId)) ?? sites[0],
    [siteId, sites],
  );
  const [selected, setSelected] = useState<LunarCoordinate>(activeSite);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(activeSite.id);
  const [hovered, setHovered] = useState<LunarCoordinate | null>(null);
  const [ready, setReady] = useState(false);
  const hasFiveMetreDem =
    selectedSiteId !== null && selectedSiteId in RENDERER_TO_TEMPLATE_ID;
  const { result: terrainWindow, loading: terrainLoading } = useTerrainWindow(
    selected,
    mode === "surface",
    hasFiveMetreDem
      ? { radiusKm: 2, samples: 513 }
      : { radiusKm: 8, samples: 257 },
  );

  useEffect(() => {
    setSelected(activeSite);
    setSelectedSiteId(activeSite.id);
  }, [activeSite]);

  const handleSelect = (coordinate: LunarCoordinate, rendererSiteId?: string) => {
    setSelected(coordinate);
    setSelectedSiteId(rendererSiteId ?? null);
    if (rendererSiteId) {
      onSelect?.(RENDERER_TO_TEMPLATE_ID[rendererSiteId] ?? rendererSiteId);
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
            {terrainWindow.dataset_id} · source {terrainWindow.native_resolution_m} m
          </div>
          <div className="text-mute">
            mesh {terrainWindow.grid.spacing_m.toFixed(1)} m · {terrainWindow.grid.rows}² vertices
          </div>
          <div className="text-mute">
            {(terrainWindow.radius_km! * 2).toFixed(0)} km field · curvature enabled
          </div>
        </div>
      )}

      {hovered && mode !== "surface" && (
        <div className="pointer-events-none absolute right-4 bottom-4 border border-line bg-black/75 px-2.5 py-1.5 font-mono text-[10px] text-soft tabular">
          {Math.abs(hovered.latitude).toFixed(4)}°{hovered.latitude < 0 ? "S" : "N"} · {Math.abs(hovered.longitude).toFixed(4)}°{hovered.longitude < 0 ? "W" : "E"}
        </div>
      )}
    </div>
  );
}
