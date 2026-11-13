import { useEffect, useMemo, useState } from "react";
import { api } from "../mvp/api";
import {
  boundsText,
  intervalAt,
  missionHours,
  missionEnd,
  timelineBins,
  type Bounds,
  type Candidate,
  type Mission,
  type PlanningResult,
  type PointResult,
  type Target,
} from "../mvp/contracts";
import { DecisionBadge } from "../mvp/DecisionBadge";
import { SITES, HIDDEN_DEFAULT_SITE_IDS, fmtTime, type Site } from "./model";
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
  return (
    <label className="block">
      <span className="eyebrow">{label}</span>
      <input
        aria-label={label}
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
export function MissionFields({
  mission: m,
  onChange,
  disabled,
}: {
  mission: Mission;
  onChange: (m: Mission) => void;
  disabled: boolean;
}) {
  const change = <K extends keyof Mission>(key: K, value: Mission[K]) => {
    const next = { ...m, [key]: value };
    if (next.timing === "end") next.hours = missionHours(next);
    else next.end = missionEnd(next);
    onChange(next);
  };
  return (
    <fieldset disabled={disabled} className="space-y-3">
      <label className="block">
        <span className="eyebrow">Define mission by</span>
        <select
          aria-label="Define mission by"
          className={`${inputClass} mt-1`}
          value={m.timing}
          onChange={(e) =>
            change("timing", e.target.value as Mission["timing"])
          }
        >
          <option value="hours">Duration in hours</option>
          <option value="end">Target end date (UTC)</option>
        </select>
      </label>
      <div
        className={`grid gap-3 ${m.timing === "end" ? "grid-cols-1" : "grid-cols-2"}`}
      >
        <label>
          <span className="eyebrow">From · UTC</span>
          <input
            className={`${inputClass} mt-1`}
            aria-label="Mission start UTC"
            type="datetime-local"
            step={300}
            value={m.start}
            onChange={(e) => change("start", e.target.value)}
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
            <span className="eyebrow">Target end · UTC</span>
            <input
              className={`${inputClass} mt-1`}
              aria-label="Mission end UTC"
              type="datetime-local"
              step={300}
              value={m.end}
              onChange={(e) => change("end", e.target.value)}
            />
          </label>
        )}
      </div>
      <p className="text-[11px] text-mute">
        {Number.isFinite(missionHours(m)) && missionHours(m) > 0
          ? `${Number(missionHours(m).toFixed(4))} hours · ends ${missionEnd(m).replace("T", " ")} UTC`
          : "Choose an end after the mission start."}
      </p>
      <details>
        <summary className="eyebrow cursor-pointer py-1">
          Mission requirements
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
            A window is continuous geometric visibility. Setup and the first
            contact must finish by the deadline.
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
            Darkness and blackout preferences are secondary; they do not reject
            a mission that meets primary requirements.
          </p>
          <label className="flex gap-2 text-xs text-soft">
            <input
              type="checkbox"
              checked={m.resolve_indeterminate}
              onChange={(e) =>
                change("resolve_indeterminate", e.target.checked)
              }
            />
            Complete inconclusive validation automatically
          </label>
          <p className="text-[11px] text-mute">
            Check conservative mission bounds first; refine the horizon up to
            twice only when needed. Requirements and validation tolerances stay
            unchanged.
          </p>
          <label className="flex gap-2 text-xs text-soft">
            <input
              type="checkbox"
              checked={m.offline}
              onChange={(e) => change("offline", e.target.checked)}
            />
            Use local astronomy data only
          </label>
        </div>
      </details>
    </fieldset>
  );
}
export function RequestStatus({
  busy,
  stage,
  error,
}: {
  busy: boolean;
  stage: string;
  error?: string;
}) {
  return (
    <>
      {busy && (
        <p role="status" className="text-xs text-sun animate-pulse">
          {stage || "Calculating"}…
        </p>
      )}
      {error && (
        <p
          role="alert"
          className="break-words text-xs leading-relaxed text-rose"
        >
          {error}
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
  const pct: Bounds | undefined = pair && [
    (pair[0] / hours) * 100,
    (pair[1] / hours) * 100,
  ];
  return (
    <div>
      <div className="flex items-center justify-between text-[13px]">
        <span className="flex items-center gap-2 text-soft">
          {icon}
          {label}
        </span>
        <span className="font-display text-lg font-semibold tabular">
          {boundsText(pct)}
          {pct ? "%" : ""}
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
          {boundsText(pair)} {label === "Mean visible Sun disc" ? "equivalent full-disc h" : "h"}
        </p>
      )}
    </div>
  );
}
export function CurrentStatus({
  result,
  time,
}: {
  result?: PointResult;
  time: number;
}) {
  const row = result && (result.instant ?? intervalAt(result.timeline, time));
  return (
    <div className="flex gap-2">
      {(["sun", "earth"] as const).map((body) => {
        const state = row?.[`${body}_state`] ?? "?";
        return (
          <div
            key={body}
            className={`flex flex-1 items-center gap-2 border px-3 py-2.5 ${state === "V" ? "border-mint/30 bg-mint/[0.06] text-mint" : state === "B" ? "border-rose/25 bg-rose/[0.05] text-rose" : "border-line text-mute"}`}
          >
            {body === "sun" ? <SunIcon size={20} /> : <EarthIcon size={20} />}
            <div>
              <p className="font-display text-sm font-semibold">
                {body === "sun" ? "Sun" : "Earth"}{" "}
                {state === "V"
                  ? "visible"
                  : state === "B"
                    ? "blocked"
                    : "unknown"}
              </p>
              <p className="font-mono text-[10px]">
                {body === "sun" && row?.sun_visible_fraction != null
                  ? `${(row.sun_visible_fraction * 100).toFixed(1)}% of disc visible`
                  : row ? "Backend interval" : "No interval evidence"}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
export function jointBounds(result: PointResult): Bounds {
  if (result.joint_hours) return result.joint_hours;
  let lo = 0,
    hi = 0;
  for (const row of result.timeline) {
    const h = (Date.parse(row.end_utc) - Date.parse(row.start_utc)) / 3600000;
    if (row.joint_state === "V") lo += h;
    if (row.joint_state !== "B") hi += h;
  }
  return [lo, hi];
}
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
  const bins = useMemo(() => timelineBins(result?.timeline ?? [], start, end), [result, start, end]);
  return (
    <div className="space-y-1.5" aria-label="Backend visibility timeline">
      {(["sun", "earth", "joint"] as const).map((body) => (
        <div key={body} className="flex items-center gap-3">
          <span className="w-10 font-mono text-[10px] uppercase text-mute">
            {body}
          </span>
          <div
            className="relative flex h-3.5 flex-1 cursor-pointer overflow-hidden bg-panel-2"
            role="img"
            aria-label={`${body}: visible, blocked or unknown across mission`}
            onClick={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              onTime(
                Math.min(
                  end - 300000,
                  Math.max(
                    start,
                    Math.floor(
                      (start +
                        ((e.clientX - box.left) / box.width) * (end - start)) /
                        300000,
                    ) * 300000,
                  ),
                ),
              );
            }}
          >
            {bins.map((r, i) => {
              const lo = r[`${body}_visible_fraction_lower`] ?? 0;
              const hi = r[`${body}_visible_fraction_upper`] ?? 1;
              const uncertain = hi-lo > 1e-9;
              return <span
                aria-hidden="true"
                key={i}
                title={`${fmtTime(Date.parse(r.start_utc))}: ${(lo * 100).toFixed(1)}${uncertain ? `–${(hi * 100).toFixed(1)}` : ""}% ${body === "sun" ? "mean Sun disc" : "visible time"} in display bin`}
                style={{
                  alignSelf: "flex-end",
                  height: uncertain ? "100%" : `${Math.max(0, lo) * 100}%`,
                  flexGrow: Date.parse(r.end_utc) - Date.parse(r.start_utc),
                  background: uncertain ? "repeating-linear-gradient(45deg,#666 0 2px,#333 2px 5px)"
                    : hi > 0 ? { sun: "#FBBF24", earth: "#06B6D4", joint: "#10B981" }[body] : "#222",
                }}
              />;
            })}
            <i
              className="pointer-events-none absolute inset-y-0 w-px bg-white"
              style={{ left: `${((time - start) / (end - start)) * 100}%` }}
            />
          </div>
        </div>
      ))}
      <p className="text-right font-mono text-[9px] text-mute">
        HEIGHT = MEAN SUN DISC / EARTH & JOINT VISIBLE TIME · HATCHED = UNCERTAIN · DISPLAY BIN AVERAGES
        {result?.timeline_transport?.exact_intervals_ready === false && " · Preview chart; exact instants available after Analyze"}
        {result?.timeline_transport?.mode === "aggregated" && result.timeline_transport.exact_intervals_ready !== false && " · Current status uses exact native intervals"}
        {!result && " · Run Analyze to load evidence"}
        {result?.timeline_transport?.mode === "pending" && (result.evaluation_stages?.validation === "not_started"
          ? " · Metrics ready · Analyze point to prepare timeline and evaluate"
          : " · Metrics ready · timeline and evaluation are being prepared")}
      </p>
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
  if ("hard_failure" in result && result.hard_failure) {
    const failure = result.hard_failure;
    return <div className="space-y-1 text-[11px] leading-relaxed text-rose" role="alert">
      <p>Hard requirement failed: {failure.constraint.replaceAll("_", " ")}.</p>
      {typeof failure.limit === "number" && failure.observed_bounds && <p>
        Required {(failure.limit * 100).toFixed(2)}%; upper bound {(failure.observed_bounds[1] * 100).toFixed(2)}%.
        {failure.shortfall_hours_bounds && ` At least ${boundsText(failure.shortfall_hours_bounds)} h short.`}
      </p>}
      <p>{failure.confirmed_sampling_minutes?.length
        ? `Hard failure confirmed on ${failure.confirmed_sampling_minutes.join("/")}-minute grids. Full validation and soft preferences skipped.`
        : "Validation and soft preferences skipped. Sampled model · PROVISIONAL."}</p>
      <p>Window: {failure.window.start_utc.replace("T", " ")} → {failure.window.end_utc.replace("T", " ")}</p>
      {failure.deadline_utc && <p>Contact must finish by {failure.deadline_utc.replace("T", " ")}.</p>}
      <p className="text-mute">{failure.explanation}</p>
      {failure.evidence_intervals.map((row) => <button key={row.start_utc} className="block text-left underline underline-offset-2"
        disabled={!onTime} onClick={() => onTime?.(Date.parse(row.at_utc ?? row.start_utc))}>
        {row.target}: {row.start_utc.replace("T", " ")} → {row.end_utc.replace("T", " ")}
        {row.at_utc && <span className="block">Worst sample: {row.at_utc.replace("T", " ")}</span>}
      </button>)}
    </div>;
  }
  if ("evaluation_status" in result && result.evaluation_status === "pending") {
    return <div role="status" className="text-[11px] leading-relaxed text-amber">
      <p>{pendingError ? "Evaluation stopped. Initial metrics remain available." : result.evaluation_stages?.validation === "not_started" ? "Prepared metrics ready. Analyze point to evaluate requirements and scientific validation." : "Evaluating requirements and scientific validation…"}</p>
      <p>Initial Sun/Earth/Joint metrics are available. Values may change after refinement; no final decision yet.</p>
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
        {result.validation.passed
          ? "Numerical checks passed"
          : result.validation.mission_path?.passed
            ? "Mission requirement bounds passed; full-model checks need review"
            : "Validation incomplete or failed"}{" "}
        · PROVISIONAL
      </p>
      {!result.validation.passed && !result.validation.mission_path?.passed && (
        <p>
          {result.decision === "FAIL"
            ? "A hard requirement failed. FAIL is retained with these validation warnings."
            : `Sampled decision ${result.nominal_sampled_decision ?? "undecided"}; PASS requires full or mission-path validation.`}
        </p>
      )}
      {result.validation.mission_path?.passed && (
        <p>
          Verified for this sampled mission only. Full-circle accuracy and
          physical DEM uncertainty are not certified.
        </p>
      )}
      {result.validation.mission_path?.metrics_hours && (
        <p>
          Conservative bounds: sunlight{" "}
          {boundsText(
            result.validation.mission_path.metrics_hours.total_sun_hours,
          )}{" "}
          h; Earth LOS{" "}
          {boundsText(
            result.validation.mission_path.metrics_hours.total_earth_los_hours,
          )}{" "}
          h.
        </p>
      )}
      {result.resolution?.enabled && (
        <p>
          {result.resolution.status === "resolved"
            ? `Revalidated: ${result.resolution.initial_decision} → ${result.decision}`
            : result.resolution.status === "not_needed"
              ? "No additional validation needed."
              : result.resolution.status === "hard_requirement_failed"
                ? "Hard requirement failed; extra validation is not required to reject this request."
                : "Additional validation could not resolve this request."}
          {!!result.resolution.refinement_rounds &&
            ` · ${result.resolution.refinement_rounds} refinement round(s)`}
          {result.resolution.error_code && ` · ${result.resolution.error_code}`}
        </p>
      )}
      {!!result.validation.reason_codes?.length && (
        <p>{result.validation.reason_codes.join(", ")}</p>
      )}
    </div>
  );
}
export function PlanningSummary({ result }: { result: PlanningResult }) {
  return (
    <section
      className="glass flex flex-wrap items-center justify-between gap-4 p-4"
      data-testid="planning-result"
    >
      <div>
        <p className="font-display text-lg">
          {result.status.replaceAll("_", " ")}
        </p>
        <p className="mt-1 text-xs text-mute">
          Evaluated {result.coverage.candidate_total} · PASS{" "}
          {result.coverage.pass} · FAIL {result.coverage.fail} · INDETERMINATE{" "}
          {result.coverage.indeterminate}
        </p>
        <p className="mt-1 text-xs text-mute">
          {result.apply_allowed
            ? "A validated feasible candidate is available."
            : "No validated feasible candidate is available."}
        </p>
      </div>
      <div className="flex gap-3">
        <a
          className={actionClass}
          href={`/api/planning/results/${result.result_id}?format=json`}
        >
          Download JSON
        </a>
        <a
          className={actionClass}
          href={`/api/planning/results/${result.result_id}?format=csv`}
        >
          Download CSV
        </a>
      </div>
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
            <dt className="text-mute">{label}</dt>
            <dd className="font-mono text-xs">
              {boundsText(c.metrics[key])} h
            </dd>
          </div>
        ))}
      </dl>
      <ValidationInfo result={c} />
      {recommended && (
        <p className="text-xs text-mint">
          {c.decision === "PASS"
            ? "Recommended among evaluated candidates"
            : "Near miss — requirements not met"}
        </p>
      )}
      <button
        className={`${actionClass} w-full`}
        disabled={!c.coordinate}
        onClick={onOpen}
      >
        View on Moon →
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
