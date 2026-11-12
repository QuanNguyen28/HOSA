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
  const [until, setUntil] = useState(() =>
    new Date(Date.parse(mission.start + "Z") + 15 * 60000)
      .toISOString()
      .slice(0, 16),
  );
  const [step, setStep] = useState(15);
  const targets = useMemo(
    () =>
      selected
        .map((id) => sites.find((t) => t.id === id))
        .filter((s): s is Site => !!s)
        .map(toTarget),
    [selected, sites],
  );
  const search = useOperation<PlanningResult>(
    JSON.stringify([mission, targets, until, step]),
  );
  const slots =
      (Date.parse(until + "Z") - Date.parse(mission.start + "Z")) /
      (step * 60000),
    count = slots * targets.length;
  const issue =
    missionIssue(mission) ??
    (!targets.length
      ? "Choose at least one site."
      : !Number.isInteger(slots) || slots <= 0
        ? "Choose an exclusive end after the start, aligned with the search step."
        : count > 128
          ? "Narrow the range or reduce targets: at most 128 evaluations per search."
          : null);
  const starts = useMemo(
    () =>
      Number.isInteger(slots) && slots > 0 && slots <= 128
        ? Array.from(
            { length: slots },
            (_, i) => Date.parse(mission.start + "Z") + i * step * 60000,
          )
        : [],
    [mission.start, slots, step],
  );
  return (
    <main className="mx-auto max-w-[1400px] space-y-5 px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <h2 className="font-display text-3xl font-semibold">
          Best dates to land
        </h2>
        <button
          className={actionClass}
          disabled={search.busy || !!issue}
          onClick={() =>
            void search.run((signal) =>
              api<PlanningResult>("/planning/windows/search", signal, {
                ...planningRequest(mission, targets),
                until_utc: new Date(until + "Z").toISOString(),
                start_step_minutes: step,
                max_results: 10,
                non_overlapping: true,
              }),
            )
          }
        >
          {search.busy ? "Searching…" : "Search dates"}
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
            <span className="eyebrow">Search starts before · UTC</span>
            <input
              aria-label="Search ends before UTC"
              className={`${inputClass} mt-1`}
              type="datetime-local"
              step={300}
              value={until}
              disabled={search.busy}
              onChange={(e) => setUntil(e.target.value)}
            />
          </label>
          <label>
            <span className="eyebrow">Start step</span>
            <select
              aria-label="Search step"
              className={`${inputClass} mt-1`}
              disabled={search.busy}
              value={step}
              onChange={(e) => setStep(Number(e.target.value))}
            >
              {[5, 15, 30, 60, 360, 1440].map((v) => (
                <option key={v} value={v}>
                  {v} minutes
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs text-mute">
            {Number.isFinite(count) ? count : "—"} candidate evaluations ·
            maximum 128
          </p>
        </div>
        <p className="text-xs leading-relaxed text-mute">
          The end is exclusive for start times. Each candidate lasts{" "}
          {missionHours(mission)} hours. Only validated PASS missions can be
          returned; returned missions at the same coordinate do not overlap.
        </p>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          {sites.map((t) => (
            <label
              key={t.id}
              className="flex items-center gap-2 text-xs text-soft"
            >
              <input
                type="checkbox"
                aria-label={t.name}
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
              {t.name}
            </label>
          ))}
        </div>
        {issue && (
          <p role="alert" className="text-xs text-rose">
            {issue}
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
            aria-label="Start date grid"
            className="glass overflow-x-auto p-4"
          >
            <div className="min-w-[620px]">
              <div className="mb-3 flex">
                <div className="w-44 shrink-0" />
                {starts.map((t) => (
                  <p
                    key={t}
                    className="flex-1 px-1 text-center font-mono text-[10px] text-mute"
                  >
                    {fmtTime(t)}
                  </p>
                ))}
              </div>
              {targets.map((target) => (
                <div key={target.id} className="mt-1 flex items-center gap-1">
                  <p className="w-44 shrink-0 truncate pr-3 text-xs text-soft">
                    {target.name}
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
                        aria-label={`${target.name}, ${fmtTime(t)}: ${candidate ? "PASS returned" : "Not returned; inspect aggregate coverage"}`}
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
              validated PASS returned
              <i className="ml-3 size-2.5 bg-mute/20" />
              not returned (not an individual FAIL classification)
            </p>
          </section>
          <section
            aria-label="Best sites"
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
              No validated feasible candidate returned. Review coverage and
              available evidence.
            </p>
          )}
        </>
      )}
    </main>
  );
}
