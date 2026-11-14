import { useTranslation } from "../i18n/language";
import { useLayoutEffect, useMemo, useState } from "react";

import { MoonScene, type GroundSky } from "../components/MoonScene";
import { useSiteAnalysis } from "../hooks/useSiteAnalysis";
import { currentInterval, intervalAt, type Interval, type MissionRequest, type PointResult } from "../mvp/contracts";
import { useSouthPolarTerrain } from "../hooks/useSouthPolarTerrain";
import { useSkyEphemeris } from "../hooks/useSkyEphemeris";
import { sampleSky } from "../lib/skyEphemeris";
import { useTerrainWindow, type TerrainWindow } from "../hooks/useTerrainWindow";
import type {
  CameraPreset,
  LayerState,
  LunarCoordinate,
  Site as RendererSite,
} from "../types";
import { EARTH_R, SUN_R, liveState, type Site } from "./model";

export type Mode = "orbit" | "pole" | "surface";

type Props = {
  mode: Mode;
  sites: Site[];
  onCoordinateSelect?: (coordinate: LunarCoordinate) => void;
  siteId: string;
  timeMs: number;
  heightM?: number;
  onSelect?: (id: string) => void;
  pointAnalysis?: PointResult | null;
  instant?: Interval;
  instantRequest?: MissionRequest;
  className?: string;
  interactive?: boolean;
};

const LAYERS: LayerState = {
  labels: true,
  grid: false,
  sites: true,
  enhancedLight: true,
};

type LocalTerrain = {
  mode: Mode;
  anchor: RendererSite;
  terrain: TerrainWindow;
  lods: Array<TerrainWindow | null>;
};

function sameCoordinate(a: LunarCoordinate | null | undefined, b: LunarCoordinate) {
  return a?.latitude === b.latitude && a.longitude === b.longitude;
}

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
  heightM,
  onSelect,
  pointAnalysis,
  instant,
  instantRequest,
  className = "",
  interactive = true,
}: Props) {
  const { t: tr } = useTranslation();
  const sites = useMemo(() => catalog.map(toRendererSite), [catalog]);
  const activeSite = useMemo(
    () => sites.find((site) => site.id === siteId) ?? sites[0],
    [siteId, sites],
  );
  const selected = activeSite;
  const selectedSiteId = activeSite.id === "custom" ? null : activeSite.id;
  // Keep the local terrain origin independent of what the user selects.
  const [focus, setFocus] = useState(() => ({ mode, anchor: selected }));
  const anchor = focus.mode === mode ? focus.anchor : selected;
  useLayoutEffect(() => {
    if (focus.mode !== mode) setFocus({ mode, anchor });
  }, [mode, anchor, focus.mode]);
  const [hovered, setHovered] = useState<LunarCoordinate | null>(null);
  const [ready, setReady] = useState(false);
  const { result: southPolarTerrain, loading: polarTerrainLoading } =
    useSouthPolarTerrain(mode === "orbit");
  const { result: terrainWindow, loading: terrainLoading } = useTerrainWindow(
    anchor,
    mode === "surface" || mode === "pole",
    { radiusKm: 1.5, samples: 401 },
  );
  const { result: midTerrainWindow, loading: midTerrainLoading } = useTerrainWindow(
    anchor,
    mode === "surface" || mode === "pole",
    { radiusKm: 6, samples: mode === "pole" ? 257 : 401 },
  );
  const { result: farTerrainWindow, loading: farTerrainLoading } = useTerrainWindow(
    anchor,
    mode === "surface" || mode === "pole",
    { radiusKm: 24, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const { result: contextTerrainWindow, loading: contextTerrainLoading } = useTerrainWindow(
    anchor,
    mode === "surface" || mode === "pole",
    { radiusKm: 48, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const { result: regionalTerrainWindow, loading: regionalTerrainLoading } = useTerrainWindow(
    anchor,
    mode === "surface" || mode === "pole",
    { radiusKm: 120, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const { result: horizonTerrainWindow, loading: horizonTerrainLoading } = useTerrainWindow(
    anchor,
    mode === "surface" || mode === "pole",
    { radiusKm: 300, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const terrainLods = useMemo(() => [
    terrainWindow, midTerrainWindow, farTerrainWindow, contextTerrainWindow,
    regionalTerrainWindow, horizonTerrainWindow,
  ], [terrainWindow, midTerrainWindow, farTerrainWindow, contextTerrainWindow,
    regionalTerrainWindow, horizonTerrainWindow]);
  const terrainPending = terrainLoading || midTerrainLoading || farTerrainLoading ||
    contextTerrainLoading || regionalTerrainLoading || horizonTerrainLoading;
  const [localTerrain, setLocalTerrain] = useState<LocalTerrain | null>(null);
  useLayoutEffect(() => {
    if (mode === "orbit" || terrainPending || !terrainWindow?.grid ||
        terrainWindow.coverage_status !== "COVERED" || !terrainWindow.geometry) return;
    setLocalTerrain((previous) => previous?.mode === mode && previous.anchor === anchor &&
      previous.terrain === terrainWindow && previous.lods === terrainLods
      ? previous : { mode, anchor, terrain: terrainWindow, lods: terrainLods });
  }, [mode, terrainPending, terrainWindow, anchor, terrainLods]);
  const visible = mode !== "orbit" && localTerrain?.mode === mode ? localTerrain : null;
  const visibleTerrain = visible?.terrain ?? null;
  const observer = mode === "orbit" ? selected : visible?.anchor ?? anchor;
  const observerIsSelected = sameCoordinate(observer, selected);
  const focusUnavailable = mode !== "orbit" && !terrainPending && !terrainWindow?.grid &&
    !sameCoordinate(visible?.anchor, anchor);
  const observerAnalysis = observerIsSelected ? pointAnalysis : null;
  const analysisSiteId = observer.id === "Site01_P1" || observer.id === "Site04_P1" ? observer.id : null;
  const { analysis } = useSiteAnalysis(analysisSiteId, new Date(timeMs));
  const skyTable = useSkyEphemeris(timeMs);
  const elevation = observerAnalysis?.coordinate.dem_elevation_m ?? visibleTerrain?.geometry?.center_elevation_m ??
    (Number.isFinite(observer.elevationM) ? observer.elevationM : 0);
  const continuousSky = useMemo(() => skyTable ? sampleSky(skyTable, timeMs, observer, elevation+(heightM ?? 2)) : undefined,
    [skyTable, timeMs, observer, elevation, heightM]);
  const groundSky = useMemo<GroundSky>(() => {
    const templateSite = catalog.find((site) => site.id === observer.id) ?? catalog[0];
    const pointSite = { ...templateSite, lat: observer.latitude, lon: observer.longitude };
    const model = liveState(pointSite, timeMs, heightM ?? 2);
    const selectedInstant = observerIsSelected && instantRequest?.panel_height_m===(heightM??2)
      && instantRequest.antenna_height_m===(heightM??2) && instant ? intervalAt([instant],timeMs) : undefined;
    const coordinateExact = (observerAnalysis?.request.panel_height_m === observerAnalysis?.request.antenna_height_m
      ? observerAnalysis && currentInterval(observerAnalysis, timeMs)
      : undefined) ?? selectedInstant;
    const exact = analysis?.availability === "AVAILABLE" ? analysis.instant : undefined;
    if (continuousSky) return {
      source: "SHARED_SPICE_PREVIEW", observerHeightM: heightM ?? 2,
      sun: { ...continuousSky.sun, angularRadiusDeg: SUN_R, state: coordinateExact?.sun_state ?? "?" },
      earth: { ...continuousSky.earth, angularRadiusDeg: EARTH_R, state: coordinateExact?.earth_state ?? "?" },
    };
    if (coordinateExact) {
      const sunAz = coordinateExact.sun_az_deg;
      const sunEl = coordinateExact.sun_el_deg;
      const earthAz = coordinateExact.earth_az_deg;
      const earthEl = coordinateExact.earth_el_deg;
      if (sunAz != null && sunEl != null && earthAz != null && earthEl != null) {
        return {
          source: observerAnalysis?.illumination?.model === "solar_disc" ? "SHARED_SPICE" : "JPL_HORIZONS",
          observerHeightM: heightM ?? 2,
          sun: {
            azimuthDeg: sunAz,
            elevationDeg: sunEl,
            angularRadiusDeg: SUN_R,
            horizonDeg: coordinateExact.sun_horizon_deg,
            clearanceDeg: coordinateExact.sun_clearance_deg,
            state: coordinateExact.sun_state,
          },
          earth: {
            azimuthDeg: earthAz,
            elevationDeg: earthEl,
            angularRadiusDeg: EARTH_R,
            horizonDeg: coordinateExact.earth_horizon_deg,
            clearanceDeg: coordinateExact.earth_clearance_deg,
            state: coordinateExact.earth_state,
          },
        };
      }
    }
    const exactSun = exact?.sun.azimuth_deg != null && exact.sun.elevation_deg != null;
    const exactEarth = exact?.earth.azimuth_deg != null && exact.earth.elevation_deg != null;
    return {
      source: exactSun && exactEarth ? "JPL_HORIZONS" : "MODEL_PREVIEW",
      observerHeightM: heightM ?? 2,
      sun: {
        azimuthDeg: exactSun ? exact!.sun.azimuth_deg! : model.b.sunAz,
        elevationDeg: exactSun ? exact!.sun.elevation_deg! : model.b.sunEl,
        angularRadiusDeg: SUN_R,
        horizonDeg: exactSun ? exact!.sun.horizon_deg : model.b.sunEl - model.sunClear,
        clearanceDeg: exactSun ? exact!.sun.clearance_deg : model.sunClear,
        state: exactSun ? exact!.sun.state : model.sun > 0 ? "V" : "B",
      },
      earth: {
        azimuthDeg: exactEarth ? exact!.earth.azimuth_deg! : model.b.earthAz,
        elevationDeg: exactEarth ? exact!.earth.elevation_deg! : model.b.earthEl,
        angularRadiusDeg: EARTH_R,
        horizonDeg: exactEarth ? exact!.earth.horizon_deg : model.b.earthEl - model.earthClear,
        clearanceDeg: exactEarth ? exact!.earth.clearance_deg : model.earthClear,
        state: exactEarth ? exact!.earth.state : model.earthUp ? "V" : "B",
      },
    };
  }, [analysis, catalog, heightM, observerAnalysis, observer, timeMs, continuousSky, instant, instantRequest, observerIsSelected]);

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
          imagery
          key={mode === "orbit" ? "globe" : "terrain"}
          time={new Date(timeMs)}
          sunVector={continuousSky?.worldSun}
          cameraPreset={modeToPreset(mode)}
          layers={LAYERS}
          sites={sites}
          selected={selected}
          terrainCoordinate={visible?.anchor}
          selectedSiteId={selectedSiteId}
          terrainWindow={visibleTerrain}
          terrainLods={visible?.lods}
          southPolarTerrain={southPolarTerrain}
          groundSky={groundSky}
          onSelect={handleSelect}
          onHover={setHovered}
          onReady={() => setReady(true)}
        />
      </div>

      <div className="pointer-events-none absolute top-16 right-4 z-10 flex w-60 flex-col items-stretch gap-2">
        {mode !== "orbit" && visible && !observerIsSelected && (
          <button type="button"
            disabled={terrainPending && sameCoordinate(anchor, selected)}
            onClick={() => setFocus({ mode, anchor: selected })}
            className="pointer-events-auto border border-line bg-black/85 px-3 py-2 text-xs text-soft hover:text-white disabled:opacity-50">
            {tr("Center on selected point")}
          </button>
        )}
        {mode === "surface" && visibleTerrain?.grid && (
          <div className="border border-line bg-black/80 px-3 py-2 font-mono text-[10px] leading-relaxed tracking-wider">
            {!observerIsSelected && <div className="mb-1 text-mute">{tr("Viewing from: ")}{observer.id === "custom" ? tr("Custom point") : observer.name}</div>}
            <div className="text-sun">{tr("☀ SUN · ")}{tr(groundSky.sun.state === "V" ? "VISIBLE" : groundSky.sun.state === "B" ? "HIDDEN" : "UNKNOWN")}</div>
            <div className="text-mute">{tr("AZ ")}{groundSky.sun.azimuthDeg.toFixed(1)}{tr("° · EL ")}{groundSky.sun.elevationDeg.toFixed(2)}{tr("° · CLR ")}{groundSky.sun.clearanceDeg == null ? "—" : groundSky.sun.clearanceDeg.toFixed(2)}°</div>
            <div className="mt-1 text-earth">{tr("⊕ EARTH · ")}{tr(groundSky.earth.state === "V" ? "VISIBLE" : groundSky.earth.state === "B" ? "HIDDEN" : "UNKNOWN")}</div>
            <div className="text-mute">{tr("AZ ")}{groundSky.earth.azimuthDeg.toFixed(1)}{tr("° · EL ")}{groundSky.earth.elevationDeg.toFixed(2)}{tr("° · CLR ")}{groundSky.earth.clearanceDeg == null ? "—" : groundSky.earth.clearanceDeg.toFixed(2)}°</div>
            <div className="mt-1 text-mute">{tr("DRAG 360° TO INSPECT THE SKY")}</div>
          </div>
        )}
      </div>


      {!ready && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-black font-mono text-[11px] tracking-widest text-mute">
          {tr("LOADING NASA LUNAR SURFACE…")}
        </div>
      )}

      {mode === "surface" && !visibleTerrain?.grid && (
        <div role="status" className="pointer-events-none absolute inset-0 grid place-items-center bg-black/80 font-mono text-[11px] tracking-widest text-mute">
          {tr(focusUnavailable ? "TERRAIN UNAVAILABLE FOR THIS POINT" : "PREPARING LOLA TERRAIN…")}
        </div>
      )}

      {mode === "surface" && visibleTerrain && (terrainPending || focusUnavailable) && (
        <div className="pointer-events-none absolute top-16 left-1/2 -translate-x-1/2 border border-line bg-black/80 px-3 py-1.5 font-mono text-[10px] tracking-wider text-soft">
          {tr(focusUnavailable ? "TERRAIN UNAVAILABLE FOR THIS POINT" : "PREPARING LOLA TERRAIN…")}
        </div>
      )}

      {mode === "pole" && (terrainPending || polarTerrainLoading) && (
        <div className="pointer-events-none absolute top-16 left-1/2 -translate-x-1/2 border border-line bg-black/80 px-3 py-1.5 font-mono text-[10px] tracking-wider text-soft">
          {tr("STREAMING NASA SOUTH-POLE TERRAIN…")}
        </div>
      )}
      {mode === "pole" && focusUnavailable && (
        <div className="pointer-events-none absolute top-16 left-1/2 -translate-x-1/2 border border-line bg-black/80 px-3 py-1.5 font-mono text-[10px] tracking-wider text-soft">
          {tr("TERRAIN UNAVAILABLE FOR THIS POINT")}
        </div>
      )}

      {mode === "pole" && visibleTerrain?.grid && (
        <div className="pointer-events-none absolute top-16 left-4 border border-line bg-black/80 px-3 py-2 font-mono text-[10px] leading-relaxed tracking-wider text-soft">
          <div className="text-mint">{tr("LOLA NESTED TERRAIN · TRUE RELIEF 1×")}</div>
          <div className="text-mute">{tr("NASA LOLA · 5 / 80 / 240 m source DEM")}</div>
          <div className="text-mute">{tr("6 circular LOD rings · south-pole flight view")}</div>
          <div className="text-sun">{tr("FOCUS LOD · 1.5 / 6 / 24 / 48 / 120 / 300 km")}</div>
          <div className="text-mute">{tr("SOURCE · ")}{tr(visibleTerrain.dataset_id ?? "regional terrain")}</div>
          <div className="text-mute">{tr('NASA IMAGE OVERLAY · DISPLAY ONLY')}</div>
          <div className="mt-1 text-mint">{tr("MOUSE · LEFT DRAG MOVE · RIGHT DRAG TILT · WHEEL ZOOM")}</div>
        </div>
      )}

      {mode === "surface" && visibleTerrain?.grid && (
        <div className="pointer-events-none absolute top-16 left-4 border border-line bg-black/80 px-3 py-2 font-mono text-[10px] leading-relaxed tracking-wider text-soft">
          <div className="text-mint">{tr("LOLA TERRAIN · TRUE SCALE 1×")}</div>
          <div className="text-mute">
            {visibleTerrain.dataset_id} {tr(" · source")}{" "}
            {visibleTerrain.native_resolution_m} {tr(" m")}</div>
          <div className="text-mute">
            {tr("mesh ")}{visibleTerrain.grid.spacing_m.toFixed(1)} {tr(" m ·")}{" "}
            {tr(visibleTerrain.grid.rows)}{tr("² vertices")}</div>
          <div className="text-mute">
            {(visibleTerrain.radius_km! * 2).toFixed(0)} {tr(" km field · curvature enabled")}</div>
          <div className="text-mute">{tr('NASA IMAGE OVERLAY · DISPLAY ONLY')}</div>
          <div className={groundSky.source !== "MODEL_PREVIEW" ? "text-mint" : "text-sun"}>
            {tr("SKY · ")}{tr(groundSky.source === "SHARED_SPICE_PREVIEW" ? "SPICE · VISUAL PREVIEW" : groundSky.source === "SHARED_SPICE" ? "SPICE / JPL CHECKED" : groundSky.source === "JPL_HORIZONS" ? "JPL HORIZONS" : "MODEL PREVIEW")}
          </div>
        </div>
      )}

      {hovered && mode !== "surface" && (
        <div className="pointer-events-none absolute right-4 bottom-4 border border-line bg-black/75 px-2.5 py-1.5 font-mono text-[10px] text-soft tabular">
          {Math.abs(hovered.latitude).toFixed(4)}°
          {tr(hovered.latitude < 0 ? "S" : "N")} ·{" "}
          {Math.abs(hovered.longitude).toFixed(4)}°
          {tr(hovered.longitude < 0 ? "W" : "E")}
        </div>
      )}
    </div>
  );
}
