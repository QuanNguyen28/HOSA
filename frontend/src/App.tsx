import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Aperture,
  ChevronDown,
  Clock3,
  Crosshair,
  Database,
  Eye,
  Grid3X3,
  Layers3,
  LocateFixed,
  MapPin,
  Maximize2,
  Moon,
  Pause,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  Sun,
} from "lucide-react";

import { MoonScene } from "./components/MoonScene";
import { CompareWorkspace } from "./components/CompareWorkspace";
import { useSites } from "./hooks/useSites";
import { useSiteAnalysis } from "./hooks/useSiteAnalysis";
import { usePointTerrain } from "./hooks/usePointTerrain";
import { useTerrainWindow } from "./hooks/useTerrainWindow";
import { formatCoordinate, formatUtc } from "./lib/lunar";
import type {
  CameraPreset,
  LayerState,
  LunarCoordinate,
} from "./types";

const START_TIME = new Date("2026-11-14T00:00:00Z");
const END_TIME = new Date("2026-12-01T00:00:00Z");

function stateLabel(state: "V" | "B" | "?" | undefined) {
  return state === "V" ? "VISIBLE" : state === "B" ? "BLOCKED" : "UNKNOWN";
}

function App() {
  const { sites, source } = useSites();
  const [time, setTime] = useState(START_TIME);
  const [isPlaying, setIsPlaying] = useState(false);
  const [cameraPreset, setCameraPreset] = useState<CameraPreset>("orbit");
  const [selected, setSelected] = useState<LunarCoordinate | null>(null);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [hovered, setHovered] = useState<LunarCoordinate | null>(null);
  const [ready, setReady] = useState(false);
  const [analysisExpanded, setAnalysisExpanded] = useState(false);
  const [workspace, setWorkspace] = useState<"explore" | "compare">("explore");
  const [layers, setLayers] = useState<LayerState>({
    labels: true,
    grid: false,
    sites: true,
    enhancedLight: true,
  });
  const { analysis, loading: analysisLoading } = useSiteAnalysis(selectedSiteId, time);
  const { result: pointTerrain, loading: pointTerrainLoading } = usePointTerrain(
    selected,
    selectedSiteId === null,
  );
  const { result: terrainWindow, loading: terrainWindowLoading } = useTerrainWindow(
    selected,
    cameraPreset === "surface" && selectedSiteId === null,
  );

  const selectedSite = useMemo(
    () => sites.find((site) => site.id === selectedSiteId) ?? null,
    [selectedSiteId, sites],
  );

  useEffect(() => {
    if (!isPlaying) return;
    let frame = 0;
    let previous = performance.now();
    const tick = (now: number) => {
      const elapsedSeconds = Math.min((now - previous) / 1000, 0.1);
      previous = now;
      setTime((current) => {
        const next = current.getTime() + elapsedSeconds * 3_600_000;
        return next >= END_TIME.getTime() ? START_TIME : new Date(next);
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [isPlaying]);

  const onSelect = useCallback((coordinate: LunarCoordinate, siteId?: string) => {
    setSelected(coordinate);
    setSelectedSiteId(siteId ?? null);
  }, []);

  const timelineValue = Math.round(
    ((time.getTime() - START_TIME.getTime()) /
      (END_TIME.getTime() - START_TIME.getTime())) *
      1000,
  );

  const toggleLayer = (key: keyof LayerState) => {
    setLayers((current) => ({ ...current, [key]: !current[key] }));
  };

  const chooseSite = (siteId: string) => {
    const site = sites.find((candidate) => candidate.id === siteId);
    if (!site) return;
    onSelect(site, site.id);
    setAnalysisExpanded(false);
    setCameraPreset("south-pole");
  };

  const chooseCamera = (preset: CameraPreset) => {
    if (
      preset === "surface" &&
      selectedSiteId !== "Site01_P1" &&
      selectedSiteId !== "Site04_P1" &&
      pointTerrain?.coverage_status !== "COVERED"
    ) {
      const detailedSite = sites.find((site) => site.id === "Site01_P1");
      if (detailedSite) onSelect(detailedSite, detailedSite.id);
      setAnalysisExpanded(false);
    }
    setCameraPreset(preset);
  };

  return (
    <main className={`app-shell workspace-${workspace}`}>
      <section className="viewport" aria-label="Interactive three-dimensional Moon">
        <MoonScene
          time={time}
          cameraPreset={cameraPreset}
          layers={layers}
          sites={sites}
          selected={selected}
          selectedSiteId={selectedSiteId}
          terrainWindow={terrainWindow}
          onSelect={onSelect}
          onHover={setHovered}
          onReady={() => setReady(true)}
        />
      </section>

      {!ready && (
        <div className="loading-screen" role="status">
          <div className="loader-orbit"><span /></div>
          <p>Loading NASA lunar surface</p>
          <small>LRO imagery · LOLA topography</small>
        </div>
      )}

      <header className="topbar glass-panel">
        <div className="brand">
          <div className="brand-mark"><Moon size={20} strokeWidth={1.5} /></div>
          <div>
            <strong>LUNARSIGHT</strong>
            <span>MOON EXPLORER</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          <button className={`nav-item ${workspace === "explore" ? "active" : ""}`} onClick={() => setWorkspace("explore")}>EXPLORE</button>
          <button className={`nav-item ${workspace === "compare" ? "active" : ""}`} onClick={() => setWorkspace("compare")}>COMPARE</button>
          <button className="nav-item" disabled title="Plan workspace is not enabled in v0.1">PLAN</button>
        </nav>
        <div className="top-actions">
          <button className="icon-button" aria-label="Search" disabled title="Search is not enabled in v0.1"><Search size={17} /></button>
          <div className="mission-pill">
            <span className="status-dot" /> DATA SIMULATION
          </div>
        </div>
      </header>

      {workspace === "compare" && <CompareWorkspace sites={sites} />}

      <aside className="left-rail">
        <div className="tool-group glass-panel">
          <button className={`tool-button ${cameraPreset === "orbit" ? "active" : ""}`} onClick={() => chooseCamera("orbit")} aria-label="Explore Moon"><Aperture size={19} /></button>
          <button className={`tool-button ${cameraPreset === "south-pole" ? "active" : ""}`} onClick={() => chooseCamera("south-pole")} aria-label="Locate south pole"><LocateFixed size={19} /></button>
          <button className={`tool-button ${layers.grid ? "active" : ""}`} onClick={() => toggleLayer("grid")} aria-label="Toggle coordinate layer"><Layers3 size={19} /></button>
          <button className="tool-button" onClick={() => document.documentElement.requestFullscreen?.()} aria-label="Fullscreen"><Maximize2 size={19} /></button>
        </div>
        <div className="tool-group glass-panel">
          <button
            className={`tool-button ${layers.grid ? "active" : ""}`}
            onClick={() => toggleLayer("grid")}
            aria-pressed={layers.grid}
            aria-label="Toggle coordinate grid"
          ><Grid3X3 size={19} /></button>
          <button
            className={`tool-button ${layers.enhancedLight ? "active" : ""}`}
            onClick={() => toggleLayer("enhancedLight")}
            aria-pressed={layers.enhancedLight}
            aria-label="Toggle enhanced lighting"
          ><Sun size={19} /></button>
        </div>
      </aside>

      <section className="context-panel glass-panel">
        <div className="eyebrow"><span /> CURRENT TARGET</div>
        <div className="target-heading">
          <div>
            <h1>MOON</h1>
            <p>Earth's natural satellite</p>
          </div>
          <button aria-label="Open target selector" disabled title="Moon is the only target in v0.1"><ChevronDown size={18} /></button>
        </div>
        <dl className="target-stats">
          <div><dt>MEAN RADIUS</dt><dd>1,737.4 <span>km</span></dd></div>
          <div><dt>GRAVITY</dt><dd>1.62 <span>m/s²</span></dd></div>
          <div><dt>DATA FRAME</dt><dd>MOON_ME</dd></div>
        </dl>
      </section>

      <aside className="analysis-panel glass-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow"><Crosshair size={13} /> SELECTED LOCATION</span>
            <h2>{selectedSite?.name ?? (selected ? "Custom point" : "No point selected")}</h2>
          </div>
          <span className={`quality-badge ${selected ? "valid" : ""}`}>
            {selectedSite ? "VERIFIED" : selected ? "UNASSESSED" : "READY"}
          </span>
        </div>

        {selected ? (
          <>
            <div className="coordinate-card">
              <MapPin size={17} />
              <div>
                <span>LATITUDE</span>
                <strong>{formatCoordinate(selected.latitude, "lat")}</strong>
              </div>
              <div>
                <span>LONGITUDE</span>
                <strong>{formatCoordinate(selected.longitude, "lon")}</strong>
              </div>
            </div>
            <div className="metric-grid">
              <article>
                <span>ELEVATION</span>
                <strong>{selectedSite ? selectedSite.elevationM.toFixed(1) : pointTerrain?.terrain?.elevation_m.toFixed(1) ?? "—"}</strong>
                <small>{selectedSite || pointTerrain?.terrain ? "metres" : pointTerrainLoading ? "Querying DEM…" : "No validated coverage"}</small>
              </article>
              <article>
                <span>TERRAIN DATA</span>
                <strong>{selectedSite ? "5 m" : pointTerrain?.terrain ? `${pointTerrain.terrain.resolution_m} m` : "—"}</strong>
                <small>{selectedSite ? "native resolution" : pointTerrain?.terrain?.dataset_id ?? "Coverage unknown"}</small>
              </article>
            </div>
            {!selectedSite && pointTerrain?.terrain?.quality && (
              <div className="quality-strip">
                <div>
                  <span>LOLA COUNT</span>
                  <strong>{pointTerrain.terrain.quality.lola_spot_count?.toFixed(0) ?? "—"}</strong>
                </div>
                <div>
                  <span>RMS ERROR</span>
                  <strong>{pointTerrain.terrain.quality.rms_error_m?.toFixed(2) ?? "—"} m</strong>
                </div>
              </div>
            )}
            {!selectedSite && pointTerrain?.terrain && (
              <div className="quality-strip">
                <div>
                  <span>LOCAL SLOPE</span>
                  <strong>{pointTerrain.terrain.slope_deg?.toFixed(2) ?? "—"}°</strong>
                </div>
                <div>
                  <span>3×3 ROUGHNESS</span>
                  <strong>{pointTerrain.terrain.local_3x3_roughness_m?.toFixed(2) ?? "—"} m</strong>
                </div>
              </div>
            )}
            {selectedSite && (
              <div className="science-card">
                <div className="science-card-title">
                  <span>LIVE GEOMETRIC STATE</span>
                  <small>{analysisLoading ? "LOADING" : analysis?.scenario_status ?? "NO DATA"}</small>
                </div>
                {analysis?.availability === "AVAILABLE" && analysis.instant ? (
                  <>
                    <div className="state-row">
                      <div><Sun size={14} /><span>SUN</span></div>
                      <strong className={`state-${analysis.instant.sun.state}`}>{stateLabel(analysis.instant.sun.state)}</strong>
                      <small>{analysis.instant.sun.clearance_deg?.toFixed(2) ?? "—"}° clearance</small>
                    </div>
                    <div className="state-row">
                      <div><Database size={14} /><span>EARTH</span></div>
                      <strong className={`state-${analysis.instant.earth.state}`}>{stateLabel(analysis.instant.earth.state)}</strong>
                      <small>{analysis.instant.earth.clearance_deg?.toFixed(2) ?? "—"}° clearance</small>
                    </div>
                    {analysis.window_72h ? (
                      <div className="window-summary">
                        <div><span>72H DECISION</span><strong>{analysis.window_72h.decision}</strong></div>
                        <div><span>MAX DARK</span><strong>{analysis.window_72h.longest_dark_hours[1].toFixed(1)} h</strong></div>
                        <div><span>MAX BLACKOUT</span><strong>{analysis.window_72h.longest_blackout_hours[1].toFixed(1)} h</strong></div>
                      </div>
                    ) : (
                      <p className="grid-only-note">72 h metrics require an exact 15-minute start. Use Compare to select a supported start index.</p>
                    )}
                    {analysisExpanded && (
                      <div className="analysis-detail">
                        <dl>
                          <div><dt>Sun az / el</dt><dd>{analysis.instant.sun.azimuth_deg?.toFixed(2)}° / {analysis.instant.sun.elevation_deg?.toFixed(2)}°</dd></div>
                          <div><dt>Earth az / el</dt><dd>{analysis.instant.earth.azimuth_deg?.toFixed(2)}° / {analysis.instant.earth.elevation_deg?.toFixed(2)}°</dd></div>
                          {analysis.window_72h && <div><dt>Total Sun · upper</dt><dd>{analysis.window_72h.total_sun_hours[1].toFixed(1)} h</dd></div>}
                          {analysis.window_72h && <div><dt>Longest joint · upper</dt><dd>{analysis.window_72h.longest_joint_hours[1].toFixed(1)} h</dd></div>}
                        </dl>
                        <p>{analysis.dataset_version} · {analysis.method_version}</p>
                      </div>
                    )}
                    <p className="provisional-note">Provisional scenario · not a landing certification</p>
                  </>
                ) : (
                  <div className="analysis-unavailable">
                    {analysisLoading ? "Reading versioned analysis…" : "Outside the validated ephemeris range."}
                  </div>
                )}
              </div>
            )}
            <button
              className="primary-action"
              disabled={!selectedSite || analysis?.availability !== "AVAILABLE"}
              onClick={() => setAnalysisExpanded((value) => !value)}
            >
              <Sparkles size={16} /> {analysisExpanded ? "HIDE ANALYSIS DETAILS" : "OPEN ANALYSIS DETAILS"}
            </button>
          </>
        ) : (
          <div className="empty-state">
            <Crosshair size={25} />
            <p>Click anywhere on the lunar surface to inspect its coordinates.</p>
          </div>
        )}

        <div className="site-list-header">
          <span>CANDIDATE SITES</span>
          <small><Database size={11} /> {source === "api" ? "API" : "v0.2.0 snapshot"}</small>
        </div>
        <div className="site-list">
          {sites.map((site) => (
            <button
              key={site.id}
              className={site.id === selectedSiteId ? "selected" : ""}
              onClick={() => chooseSite(site.id)}
            >
              <span className="site-index">{site.id.replace("_P1", "")}</span>
              <span><strong>{site.name}</strong><small>{site.id}</small></span>
              <Eye size={15} />
            </button>
          ))}
        </div>
      </aside>

      <section className="camera-presets glass-panel" aria-label="Camera presets">
        {(["orbit", "south-pole", "surface"] as CameraPreset[]).map((preset) => (
          <button
            key={preset}
            className={cameraPreset === preset ? "active" : ""}
            onClick={() => chooseCamera(preset)}
          >
            {preset === "orbit" ? "ORBIT" : preset === "south-pole" ? "SOUTH POLE" : "SURFACE"}
          </button>
        ))}
      </section>

      {cameraPreset === "surface" && (
        <div className="surface-caption glass-panel">
          <span>LOCAL TERRAIN · {selectedSiteId?.replace("_P1", "") ?? pointTerrain?.terrain?.dataset_id ?? "LOADING"}</span>
          <strong>16 × 16 km LOLA DEM</strong>
          <small>
            {terrainWindowLoading
              ? "Preparing terrain mesh…"
              : `${selectedSite ? 5 : terrainWindow?.native_resolution_m ?? pointTerrain?.terrain?.resolution_m ?? "—"} m native · visual vertical exaggeration`}
          </small>
        </div>
      )}

      {hovered && (
        <div className="cursor-readout">
          <span>{formatCoordinate(hovered.latitude, "lat")}</span>
          <span>{formatCoordinate(hovered.longitude, "lon")}</span>
        </div>
      )}

      <footer className="timeline glass-panel">
        <div className="time-readout">
          <Clock3 size={16} />
          <div><span>SIMULATION TIME · UTC</span><strong>{formatUtc(time)}</strong></div>
        </div>
        <button
          className="play-button"
          aria-label={isPlaying ? "Pause simulation" : "Play simulation"}
          onClick={() => setIsPlaying((value) => !value)}
        >{isPlaying ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}</button>
        <div className="timeline-control">
          <div className="range-labels"><span>14 NOV</span><span>17-DAY EPHEMERIS</span><span>01 DEC</span></div>
          <input
            type="range"
            min="0"
            max="1000"
            value={timelineValue}
            aria-label="Simulation time"
            onChange={(event) => {
              const fraction = Number(event.target.value) / 1000;
              setTime(new Date(START_TIME.getTime() + fraction * (END_TIME.getTime() - START_TIME.getTime())));
            }}
          />
        </div>
        <button className="speed-button" disabled title="Playback speed is fixed in v0.1">1 H / S <ChevronDown size={13} /></button>
        <button
          className="icon-button"
          aria-label="Reset time"
          onClick={() => setTime(START_TIME)}
        ><RotateCcw size={16} /></button>
      </footer>
    </main>
  );
}

export default App;
