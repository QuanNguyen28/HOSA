import { api } from "../mvp/api";
import {
  planningRequest,
  type Candidate,
  type Mission,
  type PlanningResult,
  type Target,
} from "../mvp/contracts";

/** PlanningService.search accepts at most this many start × site evaluations per request. */
export const SEARCH_LIMIT = 128;
/** Start times tried at every site, whatever the number of sites. */
export const START_SLOTS = [16, 32, 64, 128] as const;
export const MAX_RESULTS = 10;

type Requirements = {
  min_sunlit_fraction?: number | null;
  min_earth_los_fraction?: number | null;
  duration_hours: number;
};
type Key = (number | string)[];

function order(a: Key, b: Key) {
  for (let i = 0; i < Math.max(a.length, b.length); i++)
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  return 0;
}
/** ranking.display_key for rank_by total_sun_hours: conservative metric, then soft preferences. */
function displayKey(c: Candidate): Key {
  const soft = Object.values(c.soft_constraint_states ?? {});
  return [
    -(c.metrics.total_sun_hours?.[0] ?? -Infinity),
    soft.filter((v) => v === "FAIL").length,
    soft.filter((v) => v === "INDETERMINATE").length,
    c.start_utc ?? "",
    c.site_id,
  ];
}
/** metrics.violation_key: largest relative hard shortfall, then contact failures. */
function violationKey(c: Candidate, r: Requirements): Key {
  const deficits = ([
    [r.min_sunlit_fraction, "total_sun_hours"],
    [r.min_earth_los_fraction, "total_earth_los_hours"],
  ] as const)
    .filter((row): row is [number, typeof row[1]] => row[0] != null)
    .map(([limit, metric]) =>
      Math.max(0, limit - (c.metrics[metric]?.[0] ?? 0) / r.duration_hours) / Math.max(limit, 1e-9));
  const contact = Object.entries(c.constraint_states)
    .filter(([key, state]) => key.startsWith("contact.") && state === "FAIL").length;
  return [Math.max(0, ...deficits), contact];
}
/** The backend's pick order: PASS by display key, else FAIL near misses by shortfall. */
export function ranked(candidates: Candidate[], r: Requirements): Candidate[] {
  const passing = candidates.filter((c) => c.decision === "PASS");
  if (passing.length) return [...passing].sort((a, b) => order(displayKey(a), displayKey(b)));
  return candidates
    .filter((c) => c.decision === "FAIL")
    .sort((a, b) => order([...violationKey(a, r), ...displayKey(a)], [...violationKey(b, r), ...displayKey(b)]));
}

function combine(parts: PlanningResult[], candidates: Candidate[], recommended: Candidate | undefined, extra?: (c: Record<string, number>) => void, evaluations?: Candidate[]): PlanningResult {
  const coverage: Record<string, number> = {};
  for (const part of parts)
    for (const [key, value] of Object.entries(part.coverage)) coverage[key] = (coverage[key] ?? 0) + value;
  extra?.(coverage);
  return {
    ...parts[0],
    result_id: parts.map((p) => p.result_id).join("+"),
    parts: parts.map((p) => p.result_id),
    status: coverage.pass ? "FEASIBLE" : coverage.fail ? "NO_FEASIBLE_IN_EVALUATED_SET" : "INSUFFICIENT_DATA",
    candidates,
    recommended_candidate_id: recommended?.candidate_id ?? null,
    apply_allowed: candidates.some((c) => c.decision === "PASS"),
    coverage,
    warnings: [...new Set(parts.flatMap((p) => p.warnings))],
    ...(evaluations ? { evaluations } : {}),
  };
}

/** One /planning/compare answer per site, merged with the backend's recommendation rule. */
export function mergeCompare(parts: PlanningResult[], r: Requirements): PlanningResult {
  if (parts.length === 1) return parts[0];
  const candidates = parts.flatMap((p) => p.candidates);
  return combine(parts, candidates, ranked(candidates, r)[0]);
}

/**
 * One window search per site. Sites never overlap each other, so the global
 * non-overlapping top picks are the best of each site's own top picks.
 */
export function mergeSearch(parts: PlanningResult[], r: Requirements, maxResults = MAX_RESULTS): PlanningResult {
  if (parts.length === 1) return parts[0];
  const candidates = ranked(parts.flatMap((p) => p.candidates), r).slice(0, maxResults);
  return combine(parts, candidates, candidates[0], (coverage) => {
    coverage.returned = candidates.length;
    coverage.not_returned = (coverage.candidate_total ?? 0) - candidates.length;
  }, parts.flatMap((p) => p.evaluations ?? []));
}

/**
 * Rows are matched back to the ticked site by request, not by coordinate: a
 * point outside the DEM comes back INDETERMINATE without a coordinate.
 */
function forTarget(result: PlanningResult, target: Target): PlanningResult {
  const tag = (c: Candidate) => ({ ...c, target: target.id });
  return {
    ...result,
    candidates: result.candidates.map(tag),
    ...(result.evaluations ? { evaluations: result.evaluations.map(tag) } : {}),
  };
}

const answers = new Map<string, PlanningResult>();
/** Same request, same answer: re-running after adding a site only evaluates the new site. */
async function cached(path: string, body: unknown, signal: AbortSignal) {
  const key = path + JSON.stringify(body);
  const known = answers.get(key);
  if (known) return known;
  const result = await api<PlanningResult>(path, signal, body);
  answers.set(key, result);
  if (answers.size > 200) answers.delete(answers.keys().next().value!);
  return result;
}

/** Stage text stays in English here; the shared message templates translate it on display. */
const fill = (template: string, ...values: (string | number)[]) =>
  template.replace(/\{(\d+)\}/g, (_, i: string) => String(values[Number(i)]));
type Run = {
  signal: AbortSignal;
  progress: (stage: string) => void;
  publish: (value: PlanningResult) => void;
  advance: (fraction: number) => void;
};
function requirements(mission: Mission, targets: Target[]): Requirements {
  return planningRequest(mission, targets.slice(0, 1)) as Requirements;
}

export async function compareSites(mission: Mission, targets: Target[], run: Run) {
  const parts: PlanningResult[] = [];
  const r = requirements(mission, targets);
  for (const [i, target] of targets.entries()) {
    run.progress(fill("Comparing site {0} of {1} · {2}", i + 1, targets.length, target.name));
    run.advance(i / targets.length);
    parts.push(forTarget(await cached("/planning/compare", planningRequest(mission, [target]), run.signal), target));
    run.publish(mergeCompare(parts, r));
  }
  run.advance(1);
  return mergeCompare(parts, r);
}

export async function searchDates(
  mission: Mission,
  targets: Target[],
  search: { untilUtc: string; step: number },
  run: Run,
) {
  const parts: PlanningResult[] = [];
  const r = requirements(mission, targets);
  for (const [i, target] of targets.entries()) {
    run.progress(fill("Searching start times · site {0} of {1} · {2}", i + 1, targets.length, target.name));
    run.advance(i / targets.length);
    parts.push(forTarget(await cached("/planning/windows/search", {
      ...planningRequest(mission, [target]),
      until_utc: search.untilUtc,
      start_step_minutes: search.step,
      max_results: MAX_RESULTS,
      non_overlapping: true,
    }, run.signal), target));
    run.publish(mergeSearch(parts, r));
  }
  run.advance(1);
  return mergeSearch(parts, r);
}
