import { useTranslation } from "../i18n/language";
import { useMemo, useState } from "react";
import { api, useOperation } from "../mvp/api";
import {
  missionIssue,
  missionHours,
  planningRequest,
  type Candidate,
  type Mission,
  type PlanningResult,
} from "../mvp/contracts";
import { type Site, fmtTime } from "./model";

/** Same per-search cap as PlanningService.search. */
const MAX_EVALUATIONS = 128;
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

export function Finder({
  mission,
  sites,
  selected,
  onMission,
  onSelected,
  onOpen,
}: {
  mission: Mission;
  sites: Site[];
  selected: string[];
  onMission: (m: Mission) => void;
  onSelected: (v: string[]) => void;
  onOpen: (c: Candidate) => void;
}) {
  const { t: tr } = useTranslation();
  const [step, setStep] = useState(15);
  const targets = useMemo(
    () =>
      selected
        .map((id) => sites.find((t) => t.id === id))
        .filter((s): s is Site => !!s)
        .map(toTarget),
    [selected, sites],
  );
  // No separate end field: the search covers as many start times as the
  // 128-evaluation budget allows for the chosen sites and step.
  const slots = targets.length
      ? Math.min(MAX_EVALUATIONS, Math.floor(MAX_EVALUATIONS / targets.length))
      : 0,
    count = slots * targets.length;
  const startMs = Date.parse(mission.start + "Z");
  const untilMs = startMs + slots * step * 60000;
  const search = useOperation<PlanningResult>(
    JSON.stringify([mission, targets, step]),
  );
  const issue =
    missionIssue(mission) ??
    (!targets.length
      ? "Choose at least one site."
      : slots < 1
        ? "Narrow the range or reduce targets: at most 128 evaluations per search."
        : null);
  const starts = useMemo(
    () =>
      slots > 0 && Number.isFinite(startMs)
        ? Array.from({ length: slots }, (_, i) => startMs + i * step * 60000)
        : [],
    [startMs, slots, step],
  );
  return (
    <main className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <h2 className="font-display text-3xl font-semibold">
          {tr("Best dates to land")}
        </h2>
        <button
          className={actionClass}
          disabled={search.busy || !!issue}
          onClick={() =>
            void search.run((signal) =>
              api<PlanningResult>("/planning/windows/search", signal, {
                ...planningRequest(mission, targets),
                until_utc: new Date(untilMs).toISOString(),
                start_step_minutes: step,
                max_results: 10,
                non_overlapping: true,
              }),
            )
          }
        >
          {tr(search.busy ? "Searching…" : "Search dates")}
        </button>
      </div>
      <section className="glass space-y-4 p-4">
        <MissionFields
          mission={mission}
          onChange={onMission}
          disabled={search.busy}
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
          <p className="text-xs text-mute">
            {tr(count)} {tr(" candidate evaluations · maximum 128")}
            {slots > 0 && Number.isFinite(untilMs) && <>
              {" · "}{tr("tries start times until before")}{" "}
              {new Date(untilMs).toISOString().slice(0, 16).replace("T", " ") + " UTC"}
            </>}
          </p>
        </div>
        <p className="text-xs leading-relaxed text-mute">
          {tr("Each candidate lasts")}{" "}
          {tr(missionHours(mission))} {tr(" hours. Only validated PASS missions can be returned; returned missions at the same coordinate do not overlap.")}</p>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          {sites.map((t) => (
            <label
              key={t.id}
              className="flex items-center gap-2 text-xs text-soft"
            >
              <input
                type="checkbox"
                aria-label={t.id === "custom" ? tr("Custom coordinate") : t.name}
                checked={selected.includes(t.id)}
                disabled={search.busy}
                onChange={(e) =>
                  onSelected(
                    e.target.checked
                      ? [...selected, t.id]
                      : selected.filter((id) => id !== t.id),
                  )
                }
              />
              {t.id === "custom" ? tr("Custom coordinate") : t.name}
            </label>
          ))}
        </div>
        {issue && (
          <p role="alert" className="text-xs text-rose">
            {tr(issue)}
          </p>
        )}
      </section>
      <RequestStatus
        busy={search.busy}
        stage="Evaluating mission starts"
        error={search.error}
      />
      {search.result && (
        <>
          <PlanningSummary result={search.result} />
          <section
            aria-label={tr("Start date grid")}
            className="glass overflow-x-auto p-4"
          >
            <div style={{ minWidth: Math.max(620, 176 + starts.length * 8) }}>
              <div className="mb-3 flex">
                <div className="w-44 shrink-0" />
                {starts.map((t, i) => (
                  <p
                    key={t}
                    className="min-w-0 flex-1 overflow-visible whitespace-nowrap font-mono text-[10px] text-mute"
                  >
                    {/* About a dozen evenly spaced labels keep up to 128 slots legible. */}
                    {i % Math.max(1, Math.ceil(starts.length / 12)) === 0 ? fmtTime(t) : ""}
                  </p>
                ))}
              </div>
              {targets.map((target) => (
                <div key={target.id} className="mt-1 flex items-center gap-1">
                  <p className="w-44 shrink-0 truncate pr-3 text-xs text-soft">
                    {target.id === "custom" ? tr("Custom coordinate") : target.name}
                  </p>
                  {starts.map((t) => {
                    const candidate = search.result!.candidates.find(
                      (c) =>
                        Math.abs(c.coordinate!.latitude_deg - target.latitude) <
                          1e-8 &&
                        Math.abs(
                          ((c.coordinate!.longitude_e_deg -
                            target.longitude +
                            540) %
                            360) -
                            180,
                        ) < 1e-8 &&
                        Date.parse(c.start_utc) === t,
                    );
                    return (
                      <button
                        key={t}
                        type="button"
                        disabled={!candidate}
                        aria-label={tr("{0}, {1}: {2}", [target.name, fmtTime(t), candidate ? "PASS returned" : "Not returned; inspect aggregate coverage"])}
                        onClick={() => candidate && onOpen(candidate)}
                        className={`h-6 flex-1 ${candidate ? "bg-mint/70 hover:outline-1 hover:outline-white" : "bg-mute/20"}`}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
            <p className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[10px] text-mute">
              <i className="size-2.5 bg-mint/70" />
              {tr("validated PASS returned")}<i className="ml-3 size-2.5 bg-mute/20" />
              {tr("not returned (not an individual FAIL classification)")}
            </p>
          </section>
          <section
            aria-label={tr("Best sites")}
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
          >
            {search.result.candidates.map((c) => (
              <CandidateCard
                key={c.candidate_id}
                candidate={c}
                name={sites.find((t) => matches(t, c))?.name ?? c.site_id}
                hours={missionHours(mission)}
                recommended={
                  c.candidate_id === search.result!.recommended_candidate_id
                }
                onOpen={() => onOpen(c)}
              />
            ))}
          </section>
          {!search.result.candidates.length && (
            <p className="text-sm text-mute">
              {tr("No validated feasible candidate returned. Review coverage and available evidence.")}
            </p>
          )}
        </>
      )}
    </main>
  );
}
