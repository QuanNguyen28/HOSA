import { useTranslation } from "../i18n/language";
import { useEffect, useMemo, useState } from "react";

import { MoonScene, type GroundSky } from "../components/MoonScene";
import { useSiteAnalysis } from "../hooks/useSiteAnalysis";
import { currentInterval, type PointResult } from "../mvp/contracts";
import { useSouthPolarTerrain } from "../hooks/useSouthPolarTerrain";
import { useSkyEphemeris } from "../hooks/useSkyEphemeris";
import { sampleSky } from "../lib/skyEphemeris";
import type { ImageryStatus } from '../components/MoonTrekImagery';
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
  className?: string;
  interactive?: boolean;
};

const LAYERS: LayerState = {
  labels: true,
  grid: false,
  sites: true,
  enhancedLight: true,
};

type PoleTerrain = {
  coordinate: LunarCoordinate;
  terrain: TerrainWindow;
  lods: Array<TerrainWindow | null>;
  sky: GroundSky;
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
  heightM,
  onSelect,
  pointAnalysis,
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
  const [hovered, setHovered] = useState<LunarCoordinate | null>(null);
  const [ready, setReady] = useState(false);
  const [imagery,setImagery]=useState(true);
  const [imageryStatus,setImageryStatus]=useState<ImageryStatus>('loading');
  const { result: southPolarTerrain, loading: polarTerrainLoading } =
    useSouthPolarTerrain(mode === "orbit");
  const { result: terrainWindow, loading: terrainLoading } = useTerrainWindow(
    selected,
    mode === "surface" || mode === "pole",
    { radiusKm: 1.5, samples: 401 },
  );
  const { result: midTerrainWindow, loading: midTerrainLoading } = useTerrainWindow(
    selected,
    mode === "surface" || mode === "pole",
    { radiusKm: 6, samples: mode === "pole" ? 257 : 401 },
  );
  const { result: farTerrainWindow, loading: farTerrainLoading } = useTerrainWindow(
    selected,
    mode === "surface" || mode === "pole",
    { radiusKm: 24, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const { result: contextTerrainWindow, loading: contextTerrainLoading } = useTerrainWindow(
    selected,
    mode === "surface" || mode === "pole",
    { radiusKm: 48, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const { result: regionalTerrainWindow, loading: regionalTerrainLoading } = useTerrainWindow(
    selected,
    mode === "surface" || mode === "pole",
    { radiusKm: 120, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const { result: horizonTerrainWindow, loading: horizonTerrainLoading } = useTerrainWindow(
    selected,
    mode === "surface" || mode === "pole",
    { radiusKm: 300, samples: mode === "pole" ? 257 : 401, regionalOnly: true },
  );
  const analysisSiteId =
    selectedSiteId === "Site01_P1" ? "Site01_P1"
    : selectedSiteId === "Site04_P1" ? "Site04_P1"
    : null;
  const { analysis } = useSiteAnalysis(analysisSiteId, new Date(timeMs));
  const skyTable = useSkyEphemeris(timeMs);
  const elevation = pointAnalysis?.coordinate.dem_elevation_m ?? terrainWindow?.geometry?.center_elevation_m ??
    (Number.isFinite(activeSite.elevationM) ? activeSite.elevationM! : 0);
  const continuousSky = useMemo(() => skyTable ? sampleSky(skyTable, timeMs, selected, elevation+(heightM ?? 2)) : undefined,
    [skyTable, timeMs, selected, elevation, heightM]);
  const groundSky = useMemo<GroundSky>(() => {
    const templateSite = catalog.find((site) => site.id === siteId) ?? catalog[0];
    const pointSite = {
      ...templateSite,
      id: selectedSiteId ?? `custom-${selected.latitude.toFixed(4)}-${selected.longitude.toFixed(4)}`,
      lat: selected.latitude,
      lon: selected.longitude,
    };
    const model = liveState(pointSite, timeMs, heightM ?? 2);
    const coordinateExact = pointAnalysis?.request.panel_height_m === pointAnalysis?.request.antenna_height_m
      ? pointAnalysis && currentInterval(pointAnalysis, timeMs)
      : undefined;
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
          source: pointAnalysis?.illumination?.model === "solar_disc" ? "SHARED_SPICE" : "JPL_HORIZONS",
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
  }, [analysis, catalog, heightM, pointAnalysis, selected, selectedSiteId, siteId, timeMs, continuousSky]);

  const terrainLods = useMemo(() => [
    terrainWindow, midTerrainWindow, farTerrainWindow, contextTerrainWindow,
    regionalTerrainWindow, horizonTerrainWindow,
  ], [terrainWindow, midTerrainWindow, farTerrainWindow, contextTerrainWindow,
    regionalTerrainWindow, horizonTerrainWindow]);
  const terrainPending = terrainLoading || midTerrainLoading || farTerrainLoading ||
    contextTerrainLoading || regionalTerrainLoading || horizonTerrainLoading;
  const [poleTerrain, setPoleTerrain] = useState<PoleTerrain | null>(null);
  useEffect(() => {
    if (mode !== "pole" || terrainPending || !terrainWindow?.grid ||
        terrainWindow.coverage_status !== "COVERED") return;
    setPoleTerrain((previous) => previous?.terrain === terrainWindow &&
      previous.lods === terrainLods ? previous : {
        coordinate: selected, terrain: terrainWindow, lods: terrainLods, sky: groundSky,
      });
  }, [mode, terrainPending, terrainWindow, selected, terrainLods, groundSky]);
  const poleIsCurrent = poleTerrain?.coordinate.latitude === selected.latitude &&
    poleTerrain.coordinate.longitude === selected.longitude;
  const visibleTerrain = mode === "pole" ? poleTerrain?.terrain ?? null : terrainWindow;

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
          imagery={imagery && mode !== 'surface'}
          onImageryStatus={setImageryStatus}
          key={mode === "orbit" ? "globe" : "terrain"}
          time={new Date(timeMs)}
          sunVector={continuousSky?.worldSun}
          cameraPreset={modeToPreset(mode)}
          layers={LAYERS}
          sites={sites}
          selected={mode === "pole" ? poleTerrain?.coordinate ?? null : selected}
          selectedSiteId={selectedSiteId}
          terrainWindow={visibleTerrain}
          terrainLods={mode === "pole" ? poleTerrain?.lods : terrainLods}
          southPolarTerrain={southPolarTerrain}
          groundSky={mode === "pole" && !poleIsCurrent ? poleTerrain?.sky : groundSky}
          onSelect={handleSelect}
          onHover={setHovered}
          onReady={() => setReady(true)}
        />
      </div>

      {mode !== 'surface' && <div className="absolute top-16 right-4 z-10 max-w-64 border border-line bg-black/85 p-2.5 text-[10px] text-soft">
        <div className="flex gap-1" role="group" aria-label={tr('Surface appearance')}>
          <button type="button" aria-pressed={imagery} onClick={()=>setImagery(true)} className={`border px-2 py-1.5 ${imagery?'border-mint text-mint':'border-line text-mute'}`}>{tr('NASA imagery')}</button>
          <button type="button" aria-pressed={!imagery} onClick={()=>setImagery(false)} className={`border px-2 py-1.5 ${!imagery?'border-sun text-sun':'border-line text-mute'}`}>{tr('Sunlight simulation')}</button>
        </div>
        {imagery && <p className={`mt-1 ${imageryStatus==='ready'?'text-mint':'text-sun'}`} role="status">{tr(imageryStatus==='ready'?'NASA Moon Trek · imagery loaded':imageryStatus==='loading'?'Loading NASA image tiles…':imageryStatus==='partial'?'Some image tiles unavailable · lower detail retained':'NASA imagery unavailable · local preview')}</p>}
      </div>}

      {imagery && mode !== 'surface' && <a className="absolute bottom-4 left-4 z-10 border border-line bg-black/80 px-2 py-1 text-[10px] text-mute hover:text-soft" href="https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon" target="_blank" rel="noreferrer">{tr('Imagery: NASA/JPL Moon Trek · LRO/LROC')}</a>}

      {!ready && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-black font-mono text-[11px] tracking-widest text-mute">
          {tr("LOADING NASA LUNAR SURFACE…")}
        </div>
      )}

      {mode === "surface" && !terrainWindow?.grid && (
        <div role="status" className="pointer-events-none absolute inset-0 grid place-items-center bg-black/80 font-mono text-[11px] tracking-widest text-mute">
          {tr(terrainLoading ? "PREPARING LOLA TERRAIN…" : "TERRAIN UNAVAILABLE FOR THIS POINT")}
        </div>
      )}

      {mode === "surface" && (terrainLoading || midTerrainLoading || farTerrainLoading || contextTerrainLoading || regionalTerrainLoading || horizonTerrainLoading) && (
        <div className="pointer-events-none absolute top-16 left-1/2 -translate-x-1/2 border border-line bg-black/80 px-3 py-1.5 font-mono text-[10px] tracking-wider text-soft">
          {tr("PREPARING LOLA TERRAIN…")}
        </div>
      )}

      {mode === "pole" && (terrainPending || polarTerrainLoading) && (
        <div className="pointer-events-none absolute top-16 left-1/2 -translate-x-1/2 border border-line bg-black/80 px-3 py-1.5 font-mono text-[10px] tracking-wider text-soft">
          {tr("STREAMING NASA SOUTH-POLE TERRAIN…")}
        </div>
      )}
      {mode === "pole" && !terrainPending && !poleIsCurrent && !terrainWindow?.grid && (
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
          <div className="text-mute">{tr(imagery?'NASA IMAGE OVERLAY · DISPLAY ONLY':"MICRO-RELIEF · SHADING ONLY")}</div>
          <div className="mt-1 text-mint">{tr("MOUSE · LEFT DRAG MOVE · RIGHT DRAG TILT · WHEEL ZOOM")}</div>
        </div>
      )}

      {mode === "surface" && terrainWindow?.grid && (
        <div className="pointer-events-none absolute top-16 left-4 border border-line bg-black/80 px-3 py-2 font-mono text-[10px] leading-relaxed tracking-wider text-soft">
          <div className="text-mint">{tr("LOLA TERRAIN · TRUE SCALE 1×")}</div>
          <div className="text-mute">
            {terrainWindow.dataset_id} {tr(" · source")}{" "}
            {terrainWindow.native_resolution_m} {tr(" m")}</div>
          <div className="text-mute">
            {tr("mesh ")}{terrainWindow.grid.spacing_m.toFixed(1)} {tr(" m ·")}{" "}
            {tr(terrainWindow.grid.rows)}{tr("² vertices")}</div>
          <div className="text-mute">
            {(terrainWindow.radius_km! * 2).toFixed(0)} {tr(" km field · curvature enabled")}</div>
          <div className={groundSky.source !== "MODEL_PREVIEW" ? "text-mint" : "text-sun"}>
            {tr("SKY · ")}{tr(groundSky.source === "SHARED_SPICE_PREVIEW" ? "SPICE · VISUAL PREVIEW" : groundSky.source === "SHARED_SPICE" ? "SPICE / JPL CHECKED" : groundSky.source === "JPL_HORIZONS" ? "JPL HORIZONS" : "MODEL PREVIEW")}
          </div>
        </div>
      )}

      {mode === "surface" && terrainWindow?.grid && (
        <div className="pointer-events-none absolute top-16 right-4 w-48 border border-line bg-black/80 px-3 py-2 font-mono text-[10px] leading-relaxed tracking-wider">
          <div className="text-sun">{tr("☀ SUN · ")}{tr(groundSky.sun.state === "V" ? "VISIBLE" : groundSky.sun.state === "B" ? "HIDDEN" : "UNKNOWN")}</div>
          <div className="text-mute">{tr("AZ ")}{groundSky.sun.azimuthDeg.toFixed(1)}{tr("° · EL ")}{groundSky.sun.elevationDeg.toFixed(2)}{tr("° · CLR ")}{groundSky.sun.clearanceDeg == null ? "—" : groundSky.sun.clearanceDeg.toFixed(2)}°</div>
          <div className="mt-1 text-earth">{tr("⊕ EARTH · ")}{tr(groundSky.earth.state === "V" ? "VISIBLE" : groundSky.earth.state === "B" ? "HIDDEN" : "UNKNOWN")}</div>
          <div className="text-mute">{tr("AZ ")}{groundSky.earth.azimuthDeg.toFixed(1)}{tr("° · EL ")}{groundSky.earth.elevationDeg.toFixed(2)}{tr("° · CLR ")}{groundSky.earth.clearanceDeg == null ? "—" : groundSky.earth.clearanceDeg.toFixed(2)}°</div>
          <div className="mt-1 text-mute">{tr("DRAG 360° TO INSPECT THE SKY")}</div>
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
