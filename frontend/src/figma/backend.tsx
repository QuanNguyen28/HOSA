import { useTranslation } from "../i18n/language";
import { memo, useEffect, useMemo, useState } from "react";
import { api, downloadJson } from "../mvp/api";
import {
  boundsText,
  currentInterval,
  intervalAt,
  stateAt,
  sunFractionAt,
  missionHours,
  missionEnd,
  timelineBins,
  type Bounds,
  type Candidate,
  type Mission,
  type Interval,
  type PlanningResult,
  type PointResult,
  type Target,
} from "../mvp/contracts";
import { DecisionBadge } from "../mvp/DecisionBadge";
import { SITES, STEP, HIDDEN_DEFAULT_SITE_IDS, fmtTime, type Site } from "./model";
import { SunIcon, EarthIcon } from "./ui";

export const toTarget = (site: Site): Target => ({
  id: site.id,
  name: site.name,
  latitude: site.lat,
  longitude: site.lon,
  elevationM: NaN,
  status: "provisional",
});
export function useCatalog() {
  const [catalog, setCatalog] = useState<Site[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api<{
      features: Array<{
        properties: {
          site_id: string;
          region: string;
          lat_deg: number;
          lon_e_deg: number;
          dem_z_m: number;
        };
      }>;
    }>("/lunar/sites", controller.signal)
      .then((data) =>
        setCatalog(
          data.features.filter(({ properties: p }) => !HIDDEN_DEFAULT_SITE_IDS.has(p.site_id)).map(({ properties: p }) => ({
            id: p.site_id,
            name: `${p.site_id} · ${p.region}`,
            lat: p.lat_deg,
            lon: p.lon_e_deg,
            height_m: p.dem_z_m,
            group: "illumination",
            kind: "exact",
            point: "Exact backend catalog point.",
            source: "NASA LOLA backend catalog",
            url: "",
          })),
        ),
      )
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Catalog unavailable");
      });
    return () => controller.abort();
  }, []);
  return {
    sites: useMemo(() => [...SITES, ...catalog], [catalog]),
    error,
  };
}
export const inputClass =
  "w-full border border-line bg-ink px-2 py-1.5 font-mono text-xs tabular text-soft";
export const actionClass =
  "border border-white/50 px-3 py-2 font-display text-xs font-semibold tracking-widest uppercase hover:bg-white hover:text-ink disabled:cursor-not-allowed disabled:opacity-40";
export function NumberField({
  label,
  value,
  min,
  max,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  disabled?: boolean;
  onChange: (v: number) => void;
}) {
  const { t: tr } = useTranslation();
  return (
    <label className="block">
      <span className="eyebrow">{tr(label)}</span>
      <input
        aria-label={tr(label)}
        className={`${inputClass} mt-1`}
        type="number"
        min={min}
        max={max}
        step="any"
        disabled={disabled}
        value={Number.isFinite(value) ? value : ""}
        onChange={(e) =>
          onChange(e.target.value === "" ? NaN : Number(e.target.value))
        }
      />
    </label>
  );
}
/**
 * The native UTC datetime field (same typing and calendar picker as before),
 * shown as a 24-hour "YYYY-MM-DD HH:MM". Browsers draw datetime-local in the
 * UI locale, so the native text is hidden and the value is overlaid.
 */
export function DateTime24({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const { t: tr } = useTranslation();
  return (
    <span className="relative mt-1 block">
      <input
        className={`${inputClass} datetime-24`}
        aria-label={tr(label)}
        type="datetime-local"
        step={300}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-2 flex items-center font-mono text-xs tabular text-soft"
      >
        {value.replace("T", " ")}
      </span>
    </span>
  );
}
const wrapLon = (lon: number) => ((((lon + 180) % 360) + 360) % 360) - 180;
/**
 * Latitude and longitude as degrees plus a hemisphere, written the same way
 * coordinates are displayed (89.4632°S 137.4900°W), so nobody has to know
 * that south is negative. Emits signed latitude and east longitude.
 */
export function CoordinateFields({
  lat,
  lon,
  disabled,
  layout = "stack",
  onChange,
}: {
  lat: number;
  lon: number;
  disabled?: boolean;
  layout?: "stack" | "row";
  onChange: (lat: number, lon: number) => void;
}) {
  const { t: tr } = useTranslation();
  const [ns, setNs] = useState<"S" | "N">(lat > 0 ? "N" : "S");
  const [ew, setEw] = useState<"E" | "W">(wrapLon(lon) < 0 ? "W" : "E");
  // Follow a coordinate chosen elsewhere; keep the choice while a field is empty.
  useEffect(() => {
    if (Number.isFinite(lat) && lat !== 0) setNs(lat > 0 ? "N" : "S");
  }, [lat]);
  useEffect(() => {
    if (Number.isFinite(lon) && wrapLon(lon) !== 0) setEw(wrapLon(lon) < 0 ? "W" : "E");
  }, [lon]);
  const latAbs = Number.isFinite(lat) ? Math.abs(lat) : NaN;
  const lonAbs = Number.isFinite(lon) ? Math.abs(wrapLon(lon)) : NaN;
  const emit = (a: number, aSide: "S" | "N", b: number, bSide: "E" | "W") =>
    onChange(
      Number.isFinite(a) ? (aSide === "S" ? -a : a) : NaN,
      Number.isFinite(b) ? (bSide === "W" ? -b : b) : NaN,
    );
  return (
    <div className={layout === "row" ? "contents" : "space-y-3"}>
      <HemisphereField
        label="Latitude · degrees"
        value={latAbs}
        max={90}
        side={ns}
        sides={["S", "N"]}
        disabled={disabled}
        onValue={(v) => emit(v, ns, lonAbs, ew)}
        onSide={(side) => {
          setNs(side);
          emit(latAbs, side, lonAbs, ew);
        }}
      />
      <HemisphereField
        label="Longitude · degrees"
        value={lonAbs}
        max={180}
        side={ew}
        sides={["E", "W"]}
        disabled={disabled}
        onValue={(v) => emit(latAbs, ns, v, ew)}
        onSide={(side) => {
          setEw(side);
          emit(latAbs, ns, lonAbs, side);
        }}
      />
      {ns === "N" && (
        <p className="col-span-full text-[11px] text-sun">
          {tr("Terrain data covers the south polar region only; a northern point cannot be evaluated.")}
        </p>
      )}
    </div>
  );
}
function HemisphereField<S extends string>({
  label,
  value,
  max,
  side,
  sides,
  disabled,
  onValue,
  onSide,
}: {
  label: string;
  value: number;
  max: number;
  side: S;
  sides: S[];
  disabled?: boolean;
  onValue: (value: number) => void;
  onSide: (side: S) => void;
}) {
  const { t: tr } = useTranslation();
  return (
    <label className="block">
      <span className="eyebrow">{tr(label)}</span>
      <span className="mt-1 flex gap-1">
        <input
          aria-label={tr(label)}
          className={`${inputClass} min-w-0 flex-1`}
          type="number"
          min={0}
          max={max}
          step="any"
          disabled={disabled}
          value={Number.isFinite(value) ? value : ""}
          onChange={(e) => onValue(e.target.value === "" ? NaN : Number(e.target.value))}
        />
        <select
          aria-label={tr("{0} · hemisphere", [label])}
          className="shrink-0 border border-line bg-ink px-1.5 py-1.5 font-mono text-xs text-soft"
          disabled={disabled}
          value={side}
          onChange={(e) => onSide(e.target.value as S)}
        >
          {sides.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </span>
    </label>
  );
}
export function MissionFields({
  mission: m,
  onChange,
  disabled,
  durationOnly = false,
}: {
  mission: Mission;
  onChange: (m: Mission) => void;
  disabled: boolean;
  /**
   * Best dates: every candidate has its own start, so a fixed end date would
   * only fit the first one. The mission is then a duration from each start.
   */
  durationOnly?: boolean;
}) {
  const { t: tr } = useTranslation();
  const change = <K extends keyof Mission>(key: K, value: Mission[K]) => {
    const next = { ...m, [key]: value };
    if (next.timing === "end") next.hours = missionHours(next);
    else next.end = missionEnd(next);
    onChange(next);
  };
  return (
    <fieldset disabled={disabled} className="space-y-3">
      {!durationOnly && <label className="block">
        <span className="eyebrow">{tr("Define mission by")}</span>
        <select
          aria-label={tr("Define mission by")}
          className={`${inputClass} mt-1`}
          value={m.timing}
          onChange={(e) =>
            change("timing", e.target.value as Mission["timing"])
          }
        >
          <option value="hours">{tr("Duration in hours")}</option>
          <option value="end">{tr("Target end date (UTC)")}</option>
        </select>
      </label>}
      <div
        className={`grid gap-3 ${m.timing === "end" ? "grid-cols-1" : "grid-cols-2"}`}
      >
        <label>
          <span className="eyebrow">{tr(durationOnly ? "First start · UTC" : "From · UTC")}</span>
          <DateTime24
            label="Mission start UTC"
            value={m.start}
            onChange={(v) => change("start", v)}
          />
        </label>
        {m.timing === "hours" ? (
          <NumberField
            label="Mission hours"
            value={m.hours}
            min={1}
            onChange={(v) => change("hours", v)}
          />
        ) : (
          <label>
            <span className="eyebrow">{tr("Target end · UTC")}</span>
            <DateTime24
              label="Mission end UTC"
              value={m.end}
              onChange={(v) => change("end", v)}
            />
          </label>
        )}
      </div>
      <p className="text-[11px] text-mute">
        {!(Number.isFinite(missionHours(m)) && missionHours(m) > 0)
          ? tr("Choose an end after the mission start.")
          : durationOnly
            ? tr("Each candidate runs {0} hours from its own start.", [Number(missionHours(m).toFixed(4))])
            : tr("{0} hours · ends {1} UTC", [Number(missionHours(m).toFixed(4)), missionEnd(m).replace("T", " ")])}
      </p>
      <details>
        <summary className="eyebrow cursor-pointer py-1">
          {tr("Mission requirements")}
        </summary>
        <div className="mt-3 space-y-3">
          <NumberField
            label="Minimum mean visible Sun disc %"
            value={m.sun}
            min={0}
            max={100}
            onChange={(v) => change("sun", v)}
          />
          <div className="grid grid-cols-2 gap-3">
            <NumberField
              label="Panel height · m"
              value={m.panel}
              min={0.01}
              max={30}
              onChange={(v) => change("panel", v)}
            />
            <NumberField
              label="Antenna height · m"
              value={m.antenna}
              min={0.01}
              max={30}
              onChange={(v) => change("antenna", v)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField
              label="Contact duration · min"
              value={m.contact}
              min={0.01}
              max={missionHours(m) * 60}
              onChange={(v) => change("contact", v)}
            />
            <NumberField
              label="Setup · min"
              value={m.setup}
              min={0}
              max={missionHours(m) * 60}
              onChange={(v) => change("setup", v)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField
              label="Required windows"
              value={m.windows}
              min={1}
              max={1000}
              onChange={(v) => change("windows", v)}
            />
            <NumberField
              label="First contact deadline · min"
              value={m.deadline}
              min={0}
              max={missionHours(m) * 60}
              onChange={(v) => change("deadline", v)}
            />
          </div>
          <p className="text-[11px] leading-relaxed text-mute">
            {tr("A window is continuous geometric visibility. Setup and the first contact must finish by the deadline.")}
          </p>
          <NumberField
            label="Longest darkness preference · h"
            value={m.darkness}
            min={0}
            onChange={(v) => change("darkness", v)}
          />
          <NumberField
            label="Longest Earth blackout preference · h"
            value={m.blackout}
            min={0}
            onChange={(v) => change("blackout", v)}
          />
          <p className="text-[11px] text-mute">
            {tr("Darkness and blackout preferences are secondary; they do not reject a mission that meets primary requirements.")}
          </p>
          <label className="flex gap-2 text-xs text-soft">
            <input
              type="checkbox"
              checked={m.resolve_indeterminate}
              onChange={(e) =>
                change("resolve_indeterminate", e.target.checked)
              }
            />
            {tr("Complete inconclusive validation automatically")}
          </label>
          <p className="text-[11px] text-mute">
            {tr("Check conservative mission bounds first; refine the horizon up to twice only when needed. Requirements and validation tolerances stay unchanged.")}
          </p>
          <label className="flex gap-2 text-xs text-soft">
            <input
              type="checkbox"
              checked={m.offline}
              onChange={(e) => change("offline", e.target.checked)}
            />
            {tr("Use local astronomy data only")}
          </label>
        </div>
      </details>
    </fieldset>
  );
}
/**
 * Progress for long backend work. `value` (0–1) fills the bar; without it, or
 * while the current step is still running, a sweep shows the request is alive.
 */
export function RequestStatus({
  busy,
  stage,
  error,
  value,
  onCancel,
}: {
  busy: boolean;
  stage: string;
  error?: string;
  value?: number;
  onCancel?: () => void;
}) {
  const { t: tr } = useTranslation();
  const [began, setBegan] = useState<number>();
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!busy) return setBegan(undefined);
    const start = Date.now();
    setBegan(start);
    setNow(start);
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  const percent = value == null ? undefined : Math.round(value * 100);
  const elapsed = began == null ? 0 : Math.max(0, Math.round((now - began) / 1000));
  return (
    <>
      {busy && (
        <div role="status" className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-3 text-xs text-sun">
            <span className="min-w-0 break-words">{tr(stage || "Calculating")}…</span>
            <span className="shrink-0 font-mono text-[10px] tabular">
              {percent == null ? "" : `${percent}% · `}{elapsed} s
            </span>
          </div>
          <div
            role="progressbar"
            aria-label={tr("Progress")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="relative h-1.5 overflow-hidden bg-white/10"
          >
            {percent != null && (
              <div
                className="absolute inset-y-0 left-0 bg-sun transition-[width] duration-500"
                style={{ width: `${Math.max(1.5, percent)}%` }}
              />
            )}
            <div className="progress-sweep absolute inset-y-0 w-1/4 bg-gradient-to-r from-transparent via-sun/60 to-transparent" />
          </div>
          {onCancel && (
            <button
              type="button"
              className="text-[10px] text-mute underline underline-offset-2 hover:text-white"
              onClick={onCancel}
            >
              {tr("Stop")}
            </button>
          )}
        </div>
      )}
      {error && (
        <p
          role="alert"
          className="break-words text-xs leading-relaxed text-rose"
        >
          {tr(error)}
        </p>
      )}
    </>
  );
}
export function MetricBar({
  label,
  pair,
  hours,
  color,
  icon,
}: {
  label: string;
  pair?: Bounds;
  hours: number;
  color: string;
  icon?: React.ReactNode;
}) {
  const { t: tr } = useTranslation();
  const pct: Bounds | undefined = pair && [
    (pair[0] / hours) * 100,
    (pair[1] / hours) * 100,
  ];
  return (
    <div>
      <div className="flex items-center justify-between text-[13px]">
        <span className="flex items-center gap-2 text-soft">
          {icon}
          {tr(label)}
        </span>
        <span className="font-display text-lg font-semibold tabular">
          {boundsText(pct)}
          {tr(pct ? "%" : "")}
        </span>
      </div>
      <div className="mt-1.5 h-[3px] bg-line">
        {pct && (
          <div
            className="h-full"
            style={{ width: `${Math.min(100, pct[0])}%`, background: color }}
          />
        )}
      </div>
      {pair && (
        <p className="mt-1 font-mono text-[10px] text-mute">
          {boundsText(pair)} {tr(label === "Mean visible Sun disc" ? "equivalent full-disc h" : "h")}
        </p>
      )}
    </div>
  );
}
export function CurrentStatus({
  result,
  instant,
  error,
  loading,
  time,
}: {
  result?: PointResult;
  instant?: Interval;
  error?: string;
  loading?: boolean;
  time: number;
}) {
  const { t: tr } = useTranslation();
  const row = (instant && intervalAt([instant],time)) ?? (result && currentInterval(result, time));
  // Hourly prepared bins answer whenever a body kept one state for the hour.
  const fraction = sunFractionAt(result, instant, time);
  const known = stateAt(result, instant, time, "sun") !== "?" && stateAt(result, instant, time, "earth") !== "?";
  return (
    <div>
      <div className="flex gap-2">
        {(["sun", "earth"] as const).map((body) => {
          const state = stateAt(result, instant, time, body);
          return (
            <div
              key={body}
              className={`flex flex-1 items-center gap-2 border px-3 py-2.5 ${state === "V" ? "border-mint/30 bg-mint/[0.06] text-mint" : state === "B" ? "border-rose/25 bg-rose/[0.05] text-rose" : "border-line text-mute"}`}
            >
              {body === "sun" ? <SunIcon size={20} /> : <EarthIcon size={20} />}
              <div>
                <p className="font-display text-sm font-semibold">
                  {tr(body === "sun" ? "Sun" : "Earth")}{" "}
                  {tr(state === "V"
                    ? body === "sun" && fraction != null && fraction > 0 && fraction < 1
                      ? "partly visible" : "visible"
                    : state === "B"
                      ? "blocked"
                      : loading ? "loading" : "unknown")}
                </p>
                <p className="font-mono text-[10px]">
                  {body === "sun" && fraction != null
                    ? tr("{0}% of disc visible", [fraction > 0 && fraction < .001 ? "<0.1"
                      : fraction > .999 && fraction < 1 ? ">99.9" : (fraction * 100).toFixed(1)])
                    : tr(row ? "Backend interval" : state !== "?" ? "Prepared hourly state" : "No interval evidence")}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      {row?.evidence_source === "prepared_nominal" && <p className="mt-1 text-[9px] text-mute">{tr("Nominal 5-minute sample · PROVISIONAL")}</p>}
      {!row && !known && error && <p role="status" className="mt-2 text-[10px] text-sun">{tr(error==='INSTANT_NOT_PREPARED'
        ? 'No prepared instant for this coordinate/height. Analyze point to calculate it.'
        : 'Unable to load current visibility: {0}',[error])}</p>}
    </div>
  );
}
export function jointBounds(result: PointResult): Bounds {
  if (result.joint_hours) return result.joint_hours;
  let lo = 0,
    hi = 0;
  for (const row of result.timeline) {
    const h = (Date.parse(row.end_utc) - Date.parse(row.start_utc)) / 3600000;
    lo += h * (row.joint_visible_fraction_lower ?? (row.joint_state === "V" ? 1 : 0));
    hi += h * (row.joint_visible_fraction_upper ?? (row.joint_state !== "B" ? 1 : 0));
  }
  return [lo, hi];
}
// Cursor animation must not recreate up to 2,400 unchanged chart cells per frame.
const TimelineCells = memo(function TimelineCells({ bins, body }: {
  bins: Interval[]; body: "sun" | "earth" | "joint";
}) {
  const { t: tr } = useTranslation();
  return <>{bins.map((r, i) => {
    const lo = r[`${body}_visible_fraction_lower`] ?? 0;
    const hi = r[`${body}_visible_fraction_upper`] ?? 1;
    const uncertain = hi-lo > 1e-9;
    return <span
      aria-hidden="true"
      key={i}
      title={tr("{0}: {1}{2}% {3} in display bin", [fmtTime(Date.parse(r.start_utc)), boundsText([lo * 100, hi * 100], 1), "", body === "sun" ? "mean Sun disc" : "visible time"])}
      style={{
        alignSelf: "flex-end",
        height: uncertain ? "100%" : `${Math.max(0, lo) * 100}%`,
        flexGrow: Date.parse(r.end_utc) - Date.parse(r.start_utc),
        flexBasis: 0,
        flexShrink: 0,
        background: uncertain ? "repeating-linear-gradient(45deg,#666 0 2px,#333 2px 5px)"
          : hi > 0 ? { sun: "#FBBF24", earth: "#06B6D4", joint: "#10B981" }[body] : "#222",
      }}
    />;
  })}</>;
});
export function BackendTimeline({
  result,
  start,
  end,
  time,
  onTime,
}: {
  result?: PointResult;
  start: number;
  end: number;
  time: number;
  onTime: (v: number) => void;
}) {
  const { t: tr } = useTranslation();
  const timeline = result?.timeline;
  const bins = useMemo(() => timelineBins(timeline ?? [], start, end), [timeline, start, end]);
  return (
    <div className="space-y-1.5" aria-label={tr("Backend visibility timeline")}>
      {(["sun", "earth", "joint"] as const).map((body) => (
        <div key={body} className="flex items-center gap-3">
          <span className="w-10 font-mono text-[10px] uppercase text-mute">
            {tr(body)}
          </span>
          <div
            className="relative flex h-3.5 flex-1 cursor-pointer overflow-hidden bg-panel-2"
            role="img"
            aria-label={tr("{0}: visible, blocked or unknown across mission", [body])}
            onClick={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              onTime(
                Math.min(
                  end - STEP,
                  Math.max(
                    start,
                    Math.floor(
                      (start +
                        ((e.clientX - box.left) / box.width) * (end - start)) /
                        STEP,
                    ) * STEP,
                  ),
                ),
              );
            }}
          >
            <TimelineCells bins={bins} body={body} />
            <i
              className="pointer-events-none absolute inset-y-0 w-px bg-white"
              style={{ left: `${((time - start) / (end - start)) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
export function ValidationInfo({
  result,
  pendingError,
  onTime,
}: {
  result: PointResult | Candidate;
  pendingError?: string;
  onTime?: (value: number) => void;
}) {
  const { t: tr } = useTranslation();
  if ("hard_failure" in result && result.hard_failure) {
    const failure = result.hard_failure;
    return <div className="space-y-1 text-[11px] leading-relaxed text-rose" role="alert">
      <p>{tr("Hard requirement failed: ")}{tr(failure.constraint.replaceAll("_", " "))}.</p>
      {typeof failure.limit === "number" && failure.observed_bounds && <p>
        {tr("Required ")}{(failure.limit * 100).toFixed(2)}{tr("%; upper bound ")}{(failure.observed_bounds[1] * 100).toFixed(2)}%.
        {tr(failure.shortfall_hours_bounds && tr(" At least {0} h short.", [boundsText(failure.shortfall_hours_bounds)]))}
      </p>}
      <p>{tr(failure.confirmed_sampling_minutes
        ? tr("Hard failure confirmed on {0}-minute grids. Full validation and soft preferences skipped.", [failure.confirmed_sampling_minutes.join("/")])
        : "Validation and soft preferences skipped.")} {tr(" Sampled model · PROVISIONAL.")}</p>
      <p>{tr("Window: ")}{failure.window.start_utc.replace("T", " ")} → {failure.window.end_utc.replace("T", " ")}</p>
      {failure.deadline_utc && <p>{tr("Contact must finish by ")}{failure.deadline_utc.replace("T", " ")}.</p>}
      <p className="text-mute">{tr(failure.explanation)}</p>
      {failure.evidence_intervals.map((row) => <button key={row.start_utc} className="block text-left underline underline-offset-2"
        disabled={!onTime} onClick={() => onTime?.(Date.parse(row.at_utc ?? row.start_utc))}>
        {tr(row.target)}: {row.start_utc.replace("T", " ")} → {row.end_utc.replace("T", " ")}
        {row.at_utc && <span className="block">{tr("Worst sample: ")}{row.at_utc.replace("T", " ")}</span>}
      </button>)}
    </div>;
  }
  if ("evaluation_status" in result && result.evaluation_status === "pending") {
    if (!pendingError && result.evaluation_stages?.validation === "not_started") return null;
    return <div role="status" className="text-[11px] leading-relaxed text-amber">
      <p>{tr(pendingError ? "Evaluation stopped. Initial metrics remain available." : "Evaluating requirements and scientific validation…")}</p>
    </div>;
  }
  return (
    <div className="text-[11px] leading-relaxed text-mute">
      <p
        className={
          result.validation.passed || result.validation.mission_path?.passed
            ? "text-mint"
            : "text-amber"
        }
      >
        {tr(result.validation.passed
          ? "Numerical checks passed"
          : result.validation.mission_path?.passed
            ? "Mission requirement bounds passed; full-model checks need review"
            : "Validation incomplete or failed")}{" "}
        {tr("· PROVISIONAL")}
      </p>
      {!result.validation.passed && !result.validation.mission_path?.passed && (
        <p>
          {tr(result.decision === "FAIL"
            ? "A hard requirement failed. FAIL is retained with these validation warnings."
            : tr("Sampled decision {0}; PASS requires full or mission-path validation.", [result.nominal_sampled_decision ?? "undecided"]))}
        </p>
      )}
      {result.validation.mission_path?.passed && (
        <p>
          {tr("Verified for this sampled mission only. Full-circle accuracy and physical DEM uncertainty are not certified.")}
        </p>
      )}
      {result.validation.mission_path?.metrics_hours && (
        <p>
          {tr("Conservative bounds: sunlight")}{" "}
          {boundsText(
            result.validation.mission_path.metrics_hours.total_sun_hours,
          )}{" "}
          {tr("h; Earth LOS")}{" "}
          {boundsText(
            result.validation.mission_path.metrics_hours.total_earth_los_hours,
          )}{" "}
          {tr("h.")}
        </p>
      )}
      {result.resolution?.enabled && (
        <p>
          {tr(result.resolution.status === "resolved"
            ? tr("Revalidated: {0} → {1}", [result.resolution.initial_decision, result.decision])
            : result.resolution.status === "not_needed"
              ? "No additional validation needed."
              : result.resolution.status === "hard_requirement_failed"
                ? "Hard requirement failed; extra validation is not required to reject this request."
                : "Additional validation could not resolve this request.")}
          {tr(!!result.resolution.refinement_rounds &&
            tr(" · {0} refinement round(s)", [result.resolution.refinement_rounds]))}
          {tr(result.resolution.error_code && tr(" · {0}", [result.resolution.error_code]))}
        </p>
      )}
      {!!result.validation.reason_codes?.length && (
        <p>{result.validation.reason_codes.map((code) => tr(code)).join(", ")}</p>
      )}
    </div>
  );
}
export function PlanningSummary({ result }: { result: PlanningResult }) {
  const { t: tr } = useTranslation();
  return (
    <section
      className="glass flex flex-wrap items-center justify-between gap-4 p-4"
      data-testid="planning-result"
    >
      <div>
        <p className="font-display text-lg">
          {tr(result.status.replaceAll("_", " "))}
        </p>
        <p className="mt-1 text-xs text-mute">
          {tr("Evaluated ")}{tr(result.coverage.candidate_total)} {tr(" · PASS")}{" "}
          {tr(result.coverage.pass)} {tr(" · FAIL ")}{tr(result.coverage.fail)} {tr(" · INDETERMINATE")}{" "}
          {tr(result.coverage.indeterminate)}
        </p>
        <p className="mt-1 text-xs text-mute">
          {tr(result.apply_allowed
            ? "A validated feasible candidate is available."
            : "No validated feasible candidate is available.")}
        </p>
      </div>
      {result.parts && result.parts.length > 1 ? (
        // Merged from one backend request per site: the JSON is the merged
        // view; each site's own result keeps its CSV.
        <div className="flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            className={actionClass}
            onClick={() => downloadJson(result, `planning-${result.parts![0]}-merged.json`)}
          >
            {tr("Download JSON")}
          </button>
          <details className="text-xs text-mute">
            <summary className="cursor-pointer">{tr("CSV per site")}</summary>
            <div className="mt-2 flex max-w-xs flex-wrap gap-2">
              {result.parts.map((id, i) => (
                <a key={id} className="underline underline-offset-2 hover:text-white" href={`/api/planning/results/${id}?format=csv`}>
                  {tr("CSV {0}", [i + 1])}
                </a>
              ))}
            </div>
          </details>
        </div>
      ) : (
        <div className="flex gap-3">
          <a
            className={actionClass}
            href={`/api/planning/results/${result.result_id}?format=json`}
          >
            {tr("Download JSON")}
          </a>
          <a
            className={actionClass}
            href={`/api/planning/results/${result.result_id}?format=csv`}
          >
            {tr("Download CSV")}
          </a>
        </div>
      )}
    </section>
  );
}
export function CandidateCard({
  candidate: c,
  name,
  hours,
  onOpen,
  recommended,
}: {
  candidate: Candidate;
  name: string;
  hours: number;
  onOpen: () => void;
  recommended: boolean;
}) {
  const { t: tr } = useTranslation();
  return (
    <article
      className={`glass space-y-4 p-5 ${recommended ? "border-mint/40" : ""}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-display text-lg font-semibold">{name}</h3>
        <DecisionBadge value={c.decision} />
      </div>
      <p className="font-mono text-[11px] text-mute">
        {fmtTime(Date.parse(c.start_utc))}
      </p>
      <MetricBar
        label="Mean visible Sun disc"
        pair={c.metrics.total_sun_hours}
        hours={hours}
        color="#FBBF24"
        icon={<SunIcon className="text-sun" />}
      />
      <MetricBar
        label="Earth in view"
        pair={c.metrics.total_earth_los_hours}
        hours={hours}
        color="#06B6D4"
        icon={<EarthIcon className="text-earth" />}
      />
      <dl className="space-y-2 text-sm">
        {[
          ["longest_dark_hours", "Longest dark"],
          ["longest_blackout_hours", "Longest blackout"],
          ["longest_joint_hours", "Longest joint visibility"],
        ].map(([key, label]) => (
          <div
            key={key}
            className="flex justify-between gap-2 border-t border-line pt-2"
          >
            <dt className="text-mute">{tr(label)}</dt>
            <dd className="font-mono text-xs">
              {boundsText(c.metrics[key])} {tr(" h")}</dd>
          </div>
        ))}
      </dl>
      <ValidationInfo result={c} />
      {recommended && (
        <p className="text-xs text-mint">
          {tr(c.decision === "PASS"
            ? "Recommended among evaluated candidates"
            : "Near miss — requirements not met")}
        </p>
      )}
      <button
        className={`${actionClass} w-full`}
        disabled={!c.coordinate}
        onClick={onOpen}
      >
        {tr("View on Moon →")}
      </button>
    </article>
  );
}
export function matches(site: Site, c: Candidate) {
  return (
    !!c.coordinate &&
    Math.abs(site.lat - c.coordinate.latitude_deg) < 1e-8 &&
    Math.abs(((site.lon - c.coordinate.longitude_e_deg + 540) % 360) - 180) <
      1e-8
  );
}
