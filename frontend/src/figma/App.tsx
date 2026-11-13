import { useTranslation } from "../i18n/language";
import { LanguageSwitcher } from "../i18n/LanguageSwitcher";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { SITES, HEIGHTS, HIDDEN_DEFAULT_SITE_IDS, HOUR, STEP, fmtTime, type Site } from "./model";
import {
  Logo,
  SunIcon,
  EarthIcon,
  Seg,
  LiveBar,
  clamp,
  coords,
  type Shared,
} from "./ui";
import { Finder } from "./views";
import ChatDock, { ChatPage, useAssistant } from "./Chat";
import type { Mode } from "./Stage3D";
import { usePointTerrain } from "../hooks/usePointTerrain";
import { analyzePoint, api, downloadJson, useOperation, usePointInstant, usePreparedMetrics } from "../mvp/api";
import {
  DEFAULT_MISSION,
  boundsText,
  missionIssue,
  missionHours,
  missionRequest,
  planningRequest,
  type Candidate,
  type Mission,
  type PlanningResult,
  type PointResult,
} from "../mvp/contracts";
import { DecisionBadge } from "../mvp/DecisionBadge";
import {
  BackendTimeline,
  CandidateCard,
  CurrentStatus,
  MetricBar,
  MissionFields,
  NumberField,
  PlanningSummary,
  RequestStatus,
  ValidationInfo,
  actionClass,
  inputClass,
  jointBounds,
  matches,
  toTarget,
  useCatalog,
} from "./backend";

const Stage3D = lazy(() => import("./Stage3D"));
type View = "explore" | "compare" | "dates" | "chat";
const TABS: [View, string][] = [
  ["explore", "Explore"],
  ["compare", "Compare"],
  ["dates", "Best dates"],
  ["chat", "Assistant"],
];
function initialView(): View {
  const v = new URLSearchParams(location.search).get("view");
  return TABS.some(([key]) => key === v) ? (v as View) : "explore";
}
export default function App() {
  const { t: tr } = useTranslation();
  const [view, setView] = useState<View>(initialView);
  const [mission, setMission] = useState<Mission>(DEFAULT_MISSION);
  const [viewerHeight, setViewerHeight] = useState(DEFAULT_MISSION.panel);
  const { sites: catalog, error: catalogError } = useCatalog();
  const [siteId, setSiteId] = useState(
    () => {
      const requested = new URLSearchParams(location.search).get("site");
      return requested && !HIDDEN_DEFAULT_SITE_IDS.has(requested) ? requested : SITES[0].id;
    },
  );
  useEffect(() => {
    const selected = HIDDEN_DEFAULT_SITE_IDS.has(siteId) ? SITES[0].id : siteId;
    if (selected !== siteId) setSiteId(selected);
    const url = new URL(location.href);
    if (HIDDEN_DEFAULT_SITE_IDS.has(url.searchParams.get("site") ?? "")) {
      url.searchParams.set("site", selected);
      history.replaceState(null, "", url);
    }
  }, [siteId]);
  const [custom, setCustom] = useState<Site>({
    ...SITES[0],
    id: "custom",
    name: "Custom coordinate",
    kind: "approx",
    height_m: NaN,
    source: "User coordinate",
    point:
      "Coordinates entered directly; elevation is obtained from the backend DEM.",
    url: "",
  });
  const sites = useMemo(() => [...catalog, custom], [catalog, custom]);
  const site = sites.find((x) => x.id === siteId) ?? sites[0];
  const hours = missionHours(mission);
  const start = Date.parse(mission.start + "Z"),
    end = start + hours * HOUR;
  const [cursor, setCursor] = useState(Date.parse(DEFAULT_MISSION.start + "Z"));
  const time =
    Number.isFinite(start) && Number.isFinite(end)
      ? clamp(cursor, start, Math.max(start, end - STEP))
      : Date.parse(DEFAULT_MISSION.start + "Z");
  const [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(24);
  const [selected, setSelected] = useState(SITES.slice(0, 2).map((site) => site.id));
  const targets = useMemo(
    () =>
      selected
        .map((id) => sites.find((x) => x.id === id))
        .filter((x): x is Site => !!x)
        .map(toTarget),
    [selected, sites],
  );
  const point = useOperation<PointResult>(
    JSON.stringify([mission, site.lat, site.lon]),
  );
  const compared = useOperation<PlanningResult>(
    JSON.stringify([mission, targets]),
  );
  const busy = point.busy || compared.busy;
  const coordinateIssue =
    !Number.isFinite(site.lat) ||
    site.lat <= -90 ||
    site.lat >= 90 ||
    !Number.isFinite(site.lon) ||
    site.lon < -180 ||
    site.lon > 360
      ? "Use latitude between −90 and 90 (excluding poles), and longitude between −180 and 360."
      : null;
  const issue =
    missionIssue(mission) ??
    (view === "explore"
      ? coordinateIssue
      : targets.some(
            (t) =>
              !Number.isFinite(t.latitude) ||
              t.latitude <= -90 ||
              t.latitude >= 90 ||
              !Number.isFinite(t.longitude) ||
              t.longitude < -180 ||
              t.longitude > 360,
          )
        ? "Choose valid candidate coordinates."
        : null);
  const s: Shared = {
    startMs: Number.isFinite(start) ? start : time,
    endMs: Number.isFinite(end) && end > start ? end : time + HOUR,
    timeMs: time,
    playing,
    speed,
    dark: 0,
    margin: 0,
    hIdx: HEIGHTS.indexOf(viewerHeight),
  };
  const assistant = useAssistant();
  const go = (v: View) => {
    setView(v);
    setPlaying(false);
    window.scrollTo(0, 0);
  };
  const onMission = (m: Mission) => {
    if (m.panel !== mission.panel) setViewerHeight(m.panel);
    setMission(m);
    setPlaying(false);
  };
  const setH = (i: number) => {
    const height = HEIGHTS[i];
    setViewerHeight(height);
    onMission({ ...mission, panel: height, antenna: height });
  };
  const coordinate = (latitude: number, longitude: number) => {
    setCustom((old) => ({ ...old, lat: latitude, lon: longitude }));
    setSiteId("custom");
  };
  const open = (c: Candidate) => {
    if (!c.coordinate) return;
    const known = sites.find((t) => matches(t, c));
    if (known) setSiteId(known.id);
    else coordinate(c.coordinate.latitude_deg, c.coordinate.longitude_e_deg);
    onMission({
      ...mission,
      start: c.start_utc.slice(0, 16),
      end: c.end_utc.slice(0, 16),
      hours: (Date.parse(c.end_utc) - Date.parse(c.start_utc)) / HOUR,
    });
    setCursor(Date.parse(c.start_utc));
    go("explore");
  };
  useEffect(() => {
    if (!playing) return;
    let raf = 0,
      last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000);
      last = now;
      setCursor((old) => {
        const next = Math.max(start, old) + dt * speed * HOUR;
        if (next >= end - STEP) {
          setPlaying(false);
          return end - STEP;
        }
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, start, end]);
  const ctl = {
    setTime: (value: number | ((previous: number) => number)) => {
      setPlaying(false);
      setCursor(value);
    },
    setPlaying,
    setSpeed,
    setRange: (a: number, b: number) => {
      const hours = (b - a) / HOUR;
      if (Number.isFinite(hours) && Number.isInteger(hours * 12) && hours >= 1)
        onMission({
          ...mission,
          start: new Date(a).toISOString().slice(0, 16),
          end: new Date(b).toISOString().slice(0, 16),
          hours,
        });
    },
  };
  return (
    <div className="min-h-svh bg-ink">
      <header className="sticky top-0 z-40 border-b border-line bg-ink">
        <div className="flex h-14 items-center gap-1 px-2 sm:gap-4 sm:px-4 lg:px-6">
          <button
            type="button"
            onClick={() => go("explore")}
            className="flex shrink-0 items-center gap-3"
            aria-label={tr("HOSA, explore")}
          >
            <Logo size={30} />
            <span className="font-display text-[15px] font-bold tracking-[0.12em] max-sm:hidden">
              {"HOSA"}
            </span>
          </button>
          <p className="flex items-center gap-2 font-display text-[15px] font-semibold tracking-[0.06em] text-mute max-xl:hidden">
            <span aria-hidden>›</span>
            <span>{tr("South Pole")}</span>
            <span aria-hidden>›</span>
            <span className="text-white">
              {tr(TABS.find(([v]) => v === view)![1])}
            </span>
          </p>
          <nav aria-label={tr("Views")} className="ml-auto flex h-full items-stretch">
            {TABS.map(([v, l]) => (
              <button
                key={v}
                type="button"
                aria-current={view === v ? "page" : undefined}
                onClick={() => go(v)}
                className={`relative px-1 font-display text-[9px] whitespace-nowrap min-[360px]:px-1.5 min-[360px]:text-[10px] font-semibold tracking-[0.04em] uppercase transition sm:px-5 sm:tracking-[0.1em] sm:text-[13px] ${view === v ? "text-white" : "text-mute hover:text-white"}`}
              >
                <span className="sm:hidden">{tr(v === "dates" ? "Dates" : l)}</span>
                <span className="max-sm:hidden">{tr(l)}</span>
                {view === v && (
                  <span className="absolute inset-x-3 bottom-0 h-[3px] bg-white sm:inset-x-5" />
                )}
              </button>
            ))}
          </nav>
          <LanguageSwitcher />
        </div>
      </header>
      {view === "explore" && (
        <Explore
          {...{
            s,
            site,
            sites,
            mission,
            busy,
            issue,
            point,
            catalogError,
            ctl,
            setH,
            onMission,
          }}
          onSite={setSiteId}
          onCoordinate={coordinate}
          onAnalyze={() =>
            void point.run((signal, progress, preview) =>
              analyzePoint(
                missionRequest(mission, toTarget(site)),
                signal,
                progress,
                preview,
              ),
            )
          }
        />
      )}
      {view === "compare" && (
        <main className="mx-auto max-w-[1400px] space-y-4 px-4 py-6 lg:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="font-display text-3xl font-semibold">
              {tr("Compare sites")}
            </h2>
            <button
              className={actionClass}
              disabled={busy || !!issue || !targets.length}
              onClick={() =>
                void compared.run((signal) =>
                  api<PlanningResult>(
                    "/planning/compare",
                    signal,
                    planningRequest(mission, targets),
                  ),
                )
              }
            >
              {tr("Compare sites")}
            </button>
          </div>
          <section className="glass space-y-3 p-4">
            <MissionFields
              mission={mission}
              onChange={onMission}
              disabled={busy}
            />
            <p className="text-xs text-mute">
              {tr("Same mission, requirements and hardware for every candidate. Only validated PASS candidates can be recommended.")}
            </p>
            {issue && (
              <p role="alert" className="text-xs text-rose">
                {tr(issue)}
              </p>
            )}
          </section>
          <section className="grid gap-4 md:grid-cols-3">
            {Array.from(
              { length: Math.min(3, selected.length + 1) },
              (_, i) => (
                <label key={i} className="glass p-5">
                  <span className="eyebrow">{tr("Site ")}{i + 1}</span>
                  <select
                    className={`${inputClass} mt-2`}
                    aria-label={tr("Site {0}", [i + 1])}
                    value={selected[i] ?? ""}
                    disabled={busy}
                    onChange={(e) => {
                      const n = [...selected];
                      if (e.target.value) n[i] = e.target.value;
                      else n.splice(i, 1);
                      setSelected([...new Set(n)]);
                    }}
                  >
                    <option value="">{tr("— Add a site —")}</option>
                    {sites.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.id === "custom" ? tr("Custom coordinate") : t.name}
                      </option>
                    ))}
                  </select>
                </label>
              ),
            )}
          </section>
          <RequestStatus
            busy={compared.busy}
            stage="Calculating and validating candidates"
            error={compared.error}
          />
          {compared.result && (
            <>
              <PlanningSummary result={compared.result} />
              <div className="grid gap-4 md:grid-cols-3">
                {compared.result.candidates.map((c) => (
                  <CandidateCard
                    key={c.candidate_id}
                    candidate={c}
                    name={sites.find((t) => matches(t, c))?.name ?? c.site_id}
                    hours={missionHours(mission)}
                    onOpen={() => open(c)}
                    recommended={
                      compared.result!.recommended_candidate_id ===
                      c.candidate_id
                    }
                  />
                ))}
              </div>
            </>
          )}
        </main>
      )}
      {view === "dates" && (
        <Finder
          {...{ mission, sites, selected }}
          onMission={onMission}
          onSelected={setSelected}
          onOpen={open}
        />
      )}
      {view === "chat" && <ChatPage a={assistant} />}
      <ChatDock a={assistant} hidden={view === "chat"} />
    </div>
  );
}
type Operation = ReturnType<typeof useOperation<PointResult>>;
function Explore({
  s,
  site,
  sites,
  mission,
  busy: operationsBusy,
  issue,
  point,
  catalogError,
  ctl,
  setH,
  onMission,
  onSite,
  onCoordinate,
  onAnalyze,
}: {
  s: Shared;
  site: Site;
  sites: Site[];
  mission: Mission;
  busy: boolean;
  issue: string | null;
  point: Operation;
  catalogError: string;
  ctl: {
    setTime: (v: number | ((n: number) => number)) => void;
    setPlaying: (v: boolean) => void;
    setSpeed: (n: number) => void;
    setRange: (a: number, b: number) => void;
  };
  setH: (n: number) => void;
  onMission: (m: Mission) => void;
  onSite: (id: string) => void;
  onCoordinate: (lat: number, lon: number) => void;
  onAnalyze: () => void;
}) {
  const { t: tr } = useTranslation();
  const [mode, setMode] = useState<Mode>("pole");
  const [tab, setTab] = useState<"info" | "sites">("info");
  const prepared = usePreparedMetrics(issue ? undefined : missionRequest(mission, toTarget(site)));
  const r = point.result ?? prepared,
    end = s.endMs;
  const busy = operationsBusy && !r;
  const instant = usePointInstant(r, s.timeMs);
  const viewResult = useMemo(() => r ? { ...r, instant } : undefined, [r, instant]);
  const customCoordinate = useMemo(
    () => site.id === "custom" && Number.isFinite(site.lat) && Number.isFinite(site.lon)
      ? { latitude: site.lat, longitude: site.lon }
      : null,
    [site.id, site.lat, site.lon],
  );
  const { result: customTerrain, loading: terrainLoading } =
    usePointTerrain(customCoordinate, customCoordinate !== null);
  const terrain = customTerrain?.terrain;
  return (
    <div className="flex min-h-[640px] flex-col lg:h-[calc(100svh-3.5rem)] lg:flex-row">
      <aside className="flex w-full shrink-0 flex-col border-b border-line bg-panel lg:w-[340px] lg:border-r lg:border-b-0">
        <div className="flex border-b border-line" role="tablist">
          {(["info", "sites"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`px-5 py-3 font-display text-[13px] font-semibold tracking-[0.12em] uppercase ${tab === t ? "bg-ink text-white shadow-[inset_0_2px_0_#fff]" : "text-mute hover:text-white"}`}
            >
              {tr(t === "info" ? "Site" : "All sites")}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {tab === "sites" ? (
            <div className="px-2 pb-4">
              <p className="eyebrow px-3 py-3">{tr("Sites · ")}{sites.length}</p>
              {sites.map((t) => (
                <button
                  key={t.id}
                  disabled={busy}
                  onClick={() => {
                    onSite(t.id);
                    setTab("info");
                  }}
                  aria-pressed={t.id === site.id}
                  className={`flex w-full items-center gap-3 px-3 py-2.5 text-left text-[13px] ${t.id === site.id ? "bg-white/[0.07] text-white" : "text-soft hover:bg-white/[0.04]"}`}
                >
                  <i className="size-1.5 shrink-0 rounded-full bg-mute/60" />
                  <span>{t.id === "custom" ? tr("Custom coordinate") : t.name}</span>
                </button>
              ))}
              <p className="px-3 pt-3 text-[10px] text-mute">
                {tr("Location catalog only. Visibility is calculated on demand.")}
              </p>
            </div>
          ) : (
            <>
              <div className="border-b border-line p-5">
                <h2 className="text-[26px] leading-none font-bold">
                  {site.id === "custom" ? tr("Custom coordinate") : site.name}
                </h2>
                <p className="mt-2 font-mono text-xs text-mute tabular">
                  {coords(site.lat, site.lon, 4)}
                </p>
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs text-mute">
                    {tr("Choose / enter coordinates")}
                  </summary>
                  <div className="mt-3 space-y-3">
                    <label>
                      <span className="eyebrow">{tr("Location")}</span>
                      <select
                        aria-label={tr("Location")}
                        className={`${inputClass} mt-1`}
                        disabled={busy}
                        value={site.id}
                        onChange={(e) => {
                          if (e.target.value === "custom")
                            onCoordinate(site.lat, site.lon);
                          else onSite(e.target.value);
                        }}
                      >
                        {sites.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.id === "custom" ? tr("Custom coordinate") : t.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <NumberField
                      label="Latitude · degrees"
                      value={site.lat}
                      min={-89.99999999}
                      max={89.99999999}
                      disabled={busy}
                      onChange={(v) => onCoordinate(v, site.lon)}
                    />
                    <NumberField
                      label="East longitude · degrees"
                      value={site.lon}
                      min={-180}
                      max={360}
                      disabled={busy}
                      onChange={(v) => onCoordinate(site.lat, v)}
                    />
                  </div>
                </details>
              </div>
              <div className="space-y-3 border-b border-line p-5">
                <p className="eyebrow">{tr("Right now · backend intervals")}</p>
                <CurrentStatus result={viewResult} time={s.timeMs} />
              </div>
              {customCoordinate && (
                <div className="space-y-1 border-b border-line p-5 text-xs text-soft">
                  <p className="eyebrow">{tr("Point terrain")}</p>
                  {terrainLoading ? <p>{tr("Checking DEM coverage…")}</p> : terrain ? (
                    <>
                      <p>{tr("Elevation ")}{terrain.elevation_m.toFixed(1)} {tr(" m · ")}{terrain.resolution_m} {tr(" m DEM")}</p>
                      {terrain.slope_deg != null && <p>{tr("Local slope ")}{terrain.slope_deg.toFixed(2)}°</p>}
                      {terrain.local_3x3_roughness_m != null && <p>{tr("Roughness ")}{terrain.local_3x3_roughness_m.toFixed(2)} {tr(" m")}</p>}
                    </>
                  ) : customTerrain ? <p>{tr("No validated DEM covers this point.")}</p> : <p>{tr("DEM coverage unavailable.")}</p>}
                </div>
              )}
              <div className="space-y-5 border-b border-line p-5">
                <MissionFields
                  mission={mission}
                  onChange={onMission}
                  disabled={busy}
                />
                {issue && (
                  <p role="alert" className="text-xs text-rose">
                    {tr(issue)}
                  </p>
                )}
                <button
                  className={`${actionClass} w-full`}
                  disabled={point.busy || !!issue}
                  onClick={onAnalyze}
                >
                  {tr(point.busy ? "Analyzing…" : "Analyze point")}
                </button>
                <RequestStatus
                  busy={point.busy}
                  stage={point.stage}
                  error={point.error}
                />
                {!r && !point.busy && !point.error && (
                  <p className="text-xs text-mute">
                    {tr("Run Analyze point to calculate. First-time terrain preparation can take longer; astronomy uses local SPICE data.")}
                  </p>
                )}
                {r && (
                  <div data-testid="point-result" className="space-y-3">
                    <DecisionBadge value={r.evaluation_status === "pending" ? point.error ? "EVALUATION FAILED" : point.busy ? "EVALUATING" : "METRICS READY" : r.decision} />
                    <ValidationInfo result={r} pendingError={point.error} onTime={ctl.setTime} />
                    <button
                      className="text-xs text-mute underline underline-offset-2 hover:text-white"
                      onClick={() =>
                        downloadJson(r, `point-${r.result_id}.json`)
                      }
                    >
                      {tr(r.evaluation_status === "pending" ? "Download initial metrics" : r.timeline_transport?.mode === "aggregated" ? "Download summary JSON" : "Download JSON")}
                    </button>
                  </div>
                )}
                <MetricBar
                  label="Mean visible Sun disc"
                  pair={r?.metrics_hours.total_sun_hours}
                  hours={missionHours(mission)}
                  color="#FBBF24"
                  icon={<SunIcon size={14} className="text-sun" />}
                />
                <MetricBar
                  label="Earth in view"
                  pair={r?.metrics_hours.total_earth_los_hours}
                  hours={missionHours(mission)}
                  color="#06B6D4"
                  icon={<EarthIcon size={14} className="text-earth" />}
                />
                <MetricBar
                  label="Both at once"
                  pair={r ? jointBounds(r) : undefined}
                  hours={missionHours(mission)}
                  color="#10B981"
                />
                {(
                  ["longest_dark_hours", "longest_blackout_hours"] as const
                ).map((key, i) => (
                  <div
                    key={key}
                    className="flex items-center justify-between text-[13px]"
                  >
                    <span className="text-soft">
                      {tr(i ? "Longest blackout" : "Longest dark")}
                    </span>
                    <span className="font-display text-lg font-semibold tabular">
                      {boundsText(r?.metrics_hours[key])}
                      {tr(r ? " h" : "")}
                    </span>
                  </div>
                ))}
              </div>
              <div className="border-b border-line p-5">
                <p className="eyebrow mb-3">{tr("Viewer height")}</p>
                <Seg
                  label="Observer height"
                  value={s.hIdx}
                  onChange={(v) => {
                    if (!busy) setH(v);
                  }}
                  options={HEIGHTS.map((h, i) => ({
                    v: i,
                    label: i === 0 ? "Lander" : `${h} m`,
                  }))}
                />
                <p className="mt-2 text-[10px] text-mute">
                  {tr("Lander uses 2 m. Viewer presets set panel and antenna together to 2, 10, 20 or 30 m.")}
                </p>
              </div>
              <div className="space-y-3 p-5">
                <p className="eyebrow">{tr("Earth contact windows")}</p>
                {r?.contact_analysis?.visible_windows.length ? (
                  r.contact_analysis.visible_windows.map((w, i) => (
                    <button
                      key={i}
                      className="block w-full border-t border-line py-2 text-left text-xs text-soft"
                      onClick={() => ctl.setTime(Date.parse(w.start_utc))}
                    >
                      {fmtTime(Date.parse(w.start_utc))}
                      <span className="mt-1 block text-mute">
                        {w.usable_duration_minutes.toFixed(1)} {tr(" usable min ·")}{" "}
                        {tr(w.qualifies ? "Qualifies" : "Too short")}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="text-xs text-mute">
                    {tr(r?.hard_failure && !r.contact_analysis
                      ? "Contact requirements were not evaluated after the hard failure."
                      : r?.evaluation_stages?.validation === "not_started"
                      ? "Analyze point to evaluate contact requirements."
                      : r?.evaluation_status === "pending"
                      ? "Contact requirements are still being evaluated."
                      : r
                      ? "No confirmed visibility windows in this mission."
                      : "Analyze to load confirmed windows.")}
                  </p>
                )}
                {r && (
                  <details>
                    <summary className="cursor-pointer text-xs text-mute">
                      {tr("Requirements, sources & limitations")}
                    </summary>
                    <div className="mt-3 space-y-2 text-[11px] leading-relaxed text-mute">
                      {Object.entries(r.constraint_checks).map(([k, v]) => (
                        <p key={k}>
                          {tr(k.replaceAll("_", " "))}: <DecisionBadge value={v} />
                        </p>
                      ))}
                      <p>{tr("Secondary preferences")}</p>
                      {Object.entries(r.soft_constraint_checks).map(
                        ([k, v]) => (
                          <p key={k}>
                            {tr(k.replaceAll("_", " "))}:{" "}
                            <DecisionBadge value={v} />
                          </p>
                        ),
                      )}
                      <p>
                        {tr("Method ")}{tr(r.method_version)} ·{" "}
                        {tr(r.coordinate.observer_dataset_id)} ·{" "}
                        {tr(r.coordinate.observer_resolution_m)} {tr(" m DEM")}</p>
                      {r.warnings.map((w) => (
                        <p key={w}>{tr(w)}</p>
                      ))}
                    </div>
                  </details>
                )}
                <p className="text-[10px] leading-relaxed text-mute">
                  {tr("NASA LOLA + SPICE/JPL · mean solar-disc visibility / Earth-centre LOS · PROVISIONAL. No RF link or landing-safety certification.")}
                </p>
                {catalogError && (
                  <p role="alert" className="text-xs text-rose">
                    {tr("Catalog: ")}{tr(catalogError)}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </aside>
      <div className="relative min-h-[560px] flex-1">
        <Suspense
          fallback={
            <div className="absolute inset-0 grid place-items-center font-mono text-[11px] tracking-widest text-mute">
              {tr("LOADING MOON…")}
            </div>
          }
        >
          {Number.isFinite(site.lat) &&
            site.lat > -90 &&
            site.lat < 90 &&
            Number.isFinite(site.lon) &&
            site.lon >= -180 &&
            site.lon <= 360 &&
            Number.isFinite(s.timeMs) && (
              <Stage3D
                className="absolute inset-0"
                mode={mode}
                sites={sites}
                siteId={site.id}
                timeMs={s.timeMs}
                heightM={s.hIdx >= 0 ? HEIGHTS[s.hIdx] : mission.panel}
                pointAnalysis={viewResult}
                onSelect={(id) => {
                  if (!busy) {
                    onSite(id);
                    setTab("info");
                  }
                }}
                onCoordinateSelect={(c) => {
                  if (!busy) {
                    onCoordinate(c.latitude, c.longitude);
                    setTab("info");
                  }
                }}
              />
            )}
        </Suspense>
        <div className="absolute top-4 left-1/2 -translate-x-1/2">
          <Seg
            label="View"
            value={mode}
            onChange={setMode}
            options={[
              { v: "orbit", label: "Moon" },
              { v: "pole", label: "Pole" },
              { v: "surface", label: "Ground" },
            ]}
          />
        </div>
        <p className="pointer-events-none absolute top-16 right-4 max-w-[240px] text-right text-[10px] text-mute">
          {tr("3D lighting is a visual preview. Metric evidence comes from backend intervals.")}
        </p>
        <LiveBar s={s} {...ctl}>
          <BackendTimeline
            result={r}
            start={s.startMs}
            end={end}
            time={s.timeMs}
            onTime={ctl.setTime}
          />
        </LiveBar>
      </div>
    </div>
  );
}
