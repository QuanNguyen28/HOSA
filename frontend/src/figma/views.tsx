import { useTranslation } from "../i18n/language";
import { useEffect, useMemo, useState } from "react";
import { useOperation } from "../mvp/api";
import {
  DEFAULT_MISSION,
  missionIssue,
  missionHours,
  type Candidate,
  type Mission,
  type PlanningResult,
  type Target,
} from "../mvp/contracts";
import { DecisionBadge } from "../mvp/DecisionBadge";
import { type Site, fmtTime } from "./model";
import { START_SLOTS, compareSites, searchDates } from "./planning";
import {
  CandidateCard,
  MissionFields,
  PlanningSummary,
  RequestStatus,
  actionClass,
  inputClass,
  matches,
  toTarget,
} from "./backend";
import { SitePicker, chosenSites, customSites, initialChoice, type SiteChoice } from "./SitePicker";

const cellKey = (target: string, time: number) => `${target}|${time}`;
/** The ticked site a result row belongs to, by request first, coordinate second. */
const siteOf = (options: Site[], c: Candidate) =>
  options.find((t) => t.id === c.target) ?? options.find((t) => matches(t, c));
const CELL: Record<Candidate["decision"] | "NONE", string> = {
  PASS: "bg-mint/80",
  FAIL: "bg-rose/20",
  INDETERMINATE: "bg-sun/25",
  NONE: "bg-white/5",
};

/** Details of one evaluated start, with the option to show it as the site's window. */
function WindowDetail({
  name,
  row,
  hours,
  shown,
  onUse,
  onOpen,
  onClose,
}: {
  name: string;
  row: Candidate;
  hours: number;
  shown: boolean;
  onUse: () => void;
  onOpen: () => void;
  onClose: () => void;
}) {
  const { t: tr } = useTranslation();
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={tr("{0} · {1}", [name, fmtTime(Date.parse(row.start_utc))])}
        className="max-h-[90svh] w-full max-w-md space-y-3 overflow-y-auto border border-line bg-panel p-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow">{tr("Mission window")}</p>
            <p className="mt-1 font-mono text-xs text-soft">
              {fmtTime(Date.parse(row.start_utc))} → {fmtTime(Date.parse(row.end_utc))}
            </p>
          </div>
          <button type="button" aria-label={tr("Close")} className="px-2 text-lg text-mute hover:text-white" onClick={onClose}>
            ×
          </button>
        </div>
        <CandidateCard candidate={row} name={name} hours={hours} recommended={false} onOpen={onOpen} />
        <div className="space-y-1 text-[11px] text-mute">
          <p className="eyebrow">{tr("Requirements")}</p>
          {Object.entries(row.constraint_states).map(([key, state]) => (
            <p key={key} className="flex items-center justify-between gap-2">
              <span>{tr(key.replaceAll("_", " "))}</span>
              <DecisionBadge value={state} />
            </p>
          ))}
        </div>
        {shown ? (
          <p className="text-xs text-mint">{tr("This start is the window shown for this site.")}</p>
        ) : (
          <button
            type="button"
            className={`${actionClass} w-full`}
            disabled={row.decision !== "PASS"}
            onClick={onUse}
          >
            {tr("Show this window for the site")}
          </button>
        )}
        {!shown && row.decision !== "PASS" && (
          <p className="text-[11px] text-mute">
            {tr("Only a start that meets every requirement can be shown as the site's window.")}
          </p>
        )}
      </div>
    </div>
  );
}

/** Catalog sites plus this tab's own custom points, and the ticked ones as targets. */
function useChoice(sites: Site[]) {
  const { t: tr } = useTranslation();
  const [choice, setChoice] = useState<SiteChoice>(() => initialChoice(sites));
  const options = useMemo(
    () => [...sites, ...customSites(choice.customs, (i) => tr("Custom point {0}", [i]))],
    [sites, choice.customs, tr],
  );
  const chosen = useMemo(() => chosenSites(options, choice), [options, choice]);
  const targets = useMemo(() => chosen.map(toTarget), [chosen]);
  return { choice, setChoice, options, targets };
}

export function Compare({
  sites,
  hidden,
  onOpen,
}: {
  sites: Site[];
  hidden?: boolean;
  onOpen: (c: Candidate, mission: Mission) => void;
}) {
  const { t: tr } = useTranslation();
  const [mission, setMission] = useState<Mission>(DEFAULT_MISSION);
  const { choice, setChoice, options, targets } = useChoice(sites);
  const compared = useOperation<PlanningResult>(JSON.stringify([mission, targets]));
  const issue = missionIssue(mission) ?? (!targets.length ? "Choose at least one site." : null);
  return (
    <main hidden={hidden} className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-3xl space-y-1">
          <h2 className="font-display text-3xl font-semibold">{tr("Compare sites")}</h2>
          <p className="text-xs leading-relaxed text-mute">
            {tr("Evaluates every ticked site for the same mission start, duration, requirements and hardware, then recommends the best validated PASS site. Sites run one at a time; the bar counts finished sites.")}
          </p>
        </div>
        <button
          className={actionClass}
          disabled={compared.busy || !!issue}
          onClick={() =>
            void compared.run((signal, progress, publish, advance) =>
              compareSites(mission, targets, { signal, progress, publish, advance }),
            )
          }
        >
          {tr(compared.busy ? "Comparing…" : "Compare sites")}
        </button>
      </div>
      <section className="glass space-y-4 p-4">
        <MissionFields mission={mission} onChange={setMission} disabled={compared.busy} />
        <p className="text-xs text-mute">
          {tr("Same mission, requirements and hardware for every candidate. Only validated PASS candidates can be recommended.")}
        </p>
        <SitePicker sites={sites} value={choice} onChange={setChoice} disabled={compared.busy} />
        {issue && (
          <p role="alert" className="text-xs text-rose">
            {tr(issue)}
          </p>
        )}
      </section>
      <RequestStatus
        busy={compared.busy}
        stage={compared.stage}
        value={compared.fraction}
        error={compared.error}
        onCancel={compared.cancel}
      />
      {compared.result && (
        <>
          <PlanningSummary result={compared.result} />
          <div className="grid gap-4 md:grid-cols-3">
            {compared.result.candidates.map((c) => (
              <CandidateCard
                key={c.candidate_id}
                candidate={c}
                name={siteOf(options, c)?.name ?? c.site_id}
                hours={missionHours(mission)}
                onOpen={() => onOpen(c, mission)}
                recommended={compared.result!.recommended_candidate_id === c.candidate_id}
              />
            ))}
          </div>
        </>
      )}
    </main>
  );
}

export function Finder({
  sites,
  hidden,
  onOpen,
}: {
  sites: Site[];
  hidden?: boolean;
  onOpen: (c: Candidate, mission: Mission) => void;
}) {
  const { t: tr } = useTranslation();
  const [mission, setMission] = useState<Mission>(DEFAULT_MISSION);
  const [step, setStep] = useState(15);
  // Every ticked site gets the same start times; more sites mean more
  // evaluations (one backend search per site), never fewer starts per site.
  const [slots, setSlots] = useState<number>(64);
  const { choice, setChoice, options, targets } = useChoice(sites);
  const count = slots * targets.length;
  const startMs = Date.parse(mission.start + "Z");
  const untilMs = startMs + slots * step * 60000;
  const search = useOperation<PlanningResult>(JSON.stringify([mission, targets, step, slots]));
  const issue = missionIssue(mission) ?? (!targets.length ? "Choose at least one site." : null);
  const [tip, setTip] = useState<{ x: number; y: number; time: number; site: string; decision?: Candidate["decision"]; shown: boolean } | null>(null);
  const starts = useMemo(
    () => (Number.isFinite(startMs) ? Array.from({ length: slots }, (_, i) => startMs + i * step * 60000) : []),
    [startMs, slots, step],
  );
  // Every evaluated start (PASS or not), not only the backend's returned picks.
  const evaluated = useMemo(() => {
    const rows = new Map<string, Candidate>();
    const result = search.result;
    for (const row of result?.evaluations ?? result?.candidates ?? [])
      if (row.target) rows.set(cellKey(row.target, Date.parse(row.start_utc)), row);
    return rows;
  }, [search.result]);
  const at = (target: Target, time: number) => evaluated.get(cellKey(target.id, time));
  // One window per site: the earliest PASS start unless the user picked another.
  const [picked, setPicked] = useState<{ result?: string; byTarget: Record<string, number> }>({ byTarget: {} });
  const chosenStart = (target: Target) => {
    const own = picked.result === search.result?.result_id ? picked.byTarget[target.id] : undefined;
    return own ?? starts.find((t) => at(target, t)?.decision === "PASS");
  };
  const choose = (target: Target, time: number) =>
    setPicked((old) => ({
      result: search.result?.result_id,
      byTarget: { ...(old.result === search.result?.result_id ? old.byTarget : {}), [target.id]: time },
    }));
  const [detail, setDetail] = useState<{ target: Target; time: number } | null>(null);
  return (
    <main hidden={hidden} className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-3xl space-y-1">
          <h2 className="font-display text-3xl font-semibold">{tr("Best dates to land")}</h2>
          <p className="text-xs leading-relaxed text-mute">
            {tr("Tries the same mission start times at every ticked site and checks each one against every requirement. The grid shows every start; below, each site shows its earliest PASS start. Each site is searched separately; the bar counts finished sites.")}
          </p>
        </div>
        <button
          className={actionClass}
          disabled={search.busy || !!issue}
          onClick={() =>
            void search.run((signal, progress, publish, advance) =>
              searchDates(mission, targets, { untilUtc: new Date(untilMs).toISOString(), step },
                { signal, progress, publish, advance }),
            )
          }
        >
          {tr(search.busy ? "Searching…" : "Search dates")}
        </button>
      </div>
      <section className="glass space-y-4 p-4">
        <MissionFields
          mission={mission}
          onChange={(m) => setMission({ ...m, timing: "hours" })}
          disabled={search.busy}
          durationOnly
        />
        <div className="flex flex-wrap items-end gap-4">
          <label>
            <span className="eyebrow">{tr("Start step")}</span>
            <select
              aria-label={tr("Search step")}
              className={`${inputClass} mt-1`}
              disabled={search.busy}
              value={step}
              onChange={(e) => setStep(Number(e.target.value))}
            >
              {[5, 15, 30, 60, 360, 1440].map((v) => (
                <option key={v} value={v}>
                  {tr(v)} {tr(" minutes")}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="eyebrow">{tr("Start times per site")}</span>
            <select
              aria-label={tr("Start times per site")}
              className={`${inputClass} mt-1`}
              disabled={search.busy}
              value={slots}
              onChange={(e) => setSlots(Number(e.target.value))}
            >
              {START_SLOTS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </label>
          <p className="text-xs text-mute">
            {tr("{0} candidate evaluations · {1} start times × {2} sites", [count, slots, targets.length])}
            {Number.isFinite(untilMs) && <>
              {" · "}{tr("tries start times until before")}{" "}
              {new Date(untilMs).toISOString().slice(0, 16).replace("T", " ") + " UTC"}
            </>}
          </p>
        </div>
        <p className="text-xs leading-relaxed text-mute">
          {tr("Start times per site: how many mission starts are tried at each site, one every start step from the first start. Every start is a full mission check, so more start times cover a longer period but take longer.")}
        </p>
        <SitePicker sites={sites} value={choice} onChange={setChoice} disabled={search.busy} />
        {issue && (
          <p role="alert" className="text-xs text-rose">
            {tr(issue)}
          </p>
        )}
      </section>
      <RequestStatus
        busy={search.busy}
        stage={search.stage}
        value={search.fraction}
        error={search.error}
        onCancel={search.cancel}
      />
      {search.result && (
        <>
          <PlanningSummary result={search.result} />
          <section
            aria-label={tr("Start date grid")}
            className="glass overflow-x-auto p-4"
          >
            <div
              style={{ minWidth: Math.max(620, 176 + starts.length * 8) }}
              onMouseLeave={() => setTip(null)}
            >
              {targets.map((target) => {
                const shown = chosenStart(target);
                return (
                  <div key={target.id} className="mt-1 flex items-center gap-1">
                    <p className="w-44 shrink-0 truncate pr-3 text-xs text-soft">
                      {target.name}
                    </p>
                    {starts.map((t) => {
                      const row = at(target, t);
                      const show = (e: { currentTarget: HTMLElement }) => {
                        const box = e.currentTarget.getBoundingClientRect();
                        setTip({ x: box.left + box.width / 2, y: box.top, time: t, site: target.name, decision: row?.decision, shown: t === shown });
                      };
                      return (
                        // aria-disabled, not disabled: disabled buttons get no hover events.
                        <button
                          key={t}
                          type="button"
                          aria-disabled={!row}
                          aria-pressed={t === shown}
                          aria-label={tr("{0}, {1}: {2}", [target.name, fmtTime(t), row ? row.decision : "Not evaluated"])}
                          onClick={() => row && setDetail({ target, time: t })}
                          onMouseEnter={show}
                          onFocus={show}
                          onBlur={() => setTip(null)}
                          className={`h-6 flex-1 ${CELL[row?.decision ?? "NONE"]} ${t === shown ? "outline-2 -outline-offset-2 outline-white" : row ? "hover:outline-1 hover:outline-white/70" : "cursor-default"}`}
                        />
                      );
                    })}
                  </div>
                );
              })}
            </div>
            {tip && (
              // Fixed so the grid's horizontal scroll box cannot clip it.
              <div
                role="tooltip"
                className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full border border-line bg-ink px-2 py-1 font-mono text-[10px] whitespace-nowrap text-soft shadow-lg"
                style={{ left: tip.x, top: tip.y - 6 }}
              >
                <span className="block text-white">{fmtTime(tip.time)}</span>
                <span className="block text-mute">
                  {tip.site} · {tr(tip.decision ?? "Not evaluated")}
                  {tip.shown ? tr(" · shown below") : ""}
                </span>
              </div>
            )}
            <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[10px] text-mute">
              <span className="flex items-center gap-1.5"><i className={`size-2.5 ${CELL.PASS}`} />{tr("PASS · meets every requirement")}</span>
              <span className="flex items-center gap-1.5"><i className={`size-2.5 ${CELL.FAIL}`} />{tr("FAIL")}</span>
              <span className="flex items-center gap-1.5"><i className={`size-2.5 ${CELL.INDETERMINATE}`} />{tr("INDETERMINATE")}</span>
              <span className="flex items-center gap-1.5"><i className="size-2.5 outline-2 -outline-offset-2 outline-white" />{tr("window shown below")}</span>
              <span>{tr("Click a cell for details.")}</span>
            </p>
          </section>
          <section aria-label={tr("Best sites")} className="space-y-3">
            <p className="text-xs text-mute">
              {tr("One window per site: the earliest start that meets every requirement. Click any PASS cell above to show a different start.")}
            </p>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {targets.map((target) => {
                const time = chosenStart(target);
                const row = time == null ? undefined : at(target, time);
                return row ? (
                  <CandidateCard
                    key={target.id}
                    candidate={row}
                    name={target.name}
                    hours={missionHours(mission)}
                    recommended={false}
                    onOpen={() => onOpen(row, mission)}
                  />
                ) : (
                  <article key={target.id} className="glass space-y-2 p-5">
                    <h3 className="font-display text-lg font-semibold">{target.name}</h3>
                    <p className="text-xs text-mute">
                      {tr(starts.some((t) => at(target, t)?.validation.reason_codes?.includes("OUTSIDE_DEM_COVERAGE"))
                        ? "Outside the south polar terrain (DEM) coverage, so no start could be evaluated."
                        : "No start time in the searched range met every requirement.")}
                    </p>
                  </article>
                );
              })}
            </div>
          </section>
          {detail && (
            <WindowDetail
              name={detail.target.name}
              row={at(detail.target, detail.time)!}
              hours={missionHours(mission)}
              shown={chosenStart(detail.target) === detail.time}
              onUse={() => {
                choose(detail.target, detail.time);
                setDetail(null);
              }}
              onOpen={() => onOpen(at(detail.target, detail.time)!, mission)}
              onClose={() => setDetail(null)}
            />
          )}
        </>
      )}
    </main>
  );
}
