import { describe, expect, it } from "vitest";
import type { Candidate, PlanningResult, PointResult } from "../mvp/contracts";
import { intervalAt, stateAt } from "../mvp/contracts";
import { mergeCompare, mergeSearch, ranked } from "./planning";
import { SITES } from "./model";
import { PLANNING_EXCLUDED, chosenSites, customSites, initialChoice } from "./SitePicker";

const candidate = (id: string, site: string, start: string, decision: Candidate["decision"], sun: number, extra: Partial<Candidate> = {}): Candidate => ({
  candidate_id: id,
  site_id: site,
  start_utc: start,
  end_utc: start,
  decision,
  nominal_sampled_decision: null,
  metrics: { total_sun_hours: [sun, sun + 1], total_earth_los_hours: [60, 60] },
  constraint_states: {},
  validation: { passed: decision === "PASS", reason_codes: [] },
  ...extra,
});
const result = (id: string, candidates: Candidate[], coverage: Record<string, number>): PlanningResult => ({
  result_id: id,
  operation: "window_search",
  status: coverage.pass ? "FEASIBLE" : "NO_FEASIBLE_IN_EVALUATED_SET",
  candidates,
  recommended_candidate_id: candidates[0]?.candidate_id ?? null,
  apply_allowed: candidates.some((c) => c.decision === "PASS"),
  coverage,
  method_version: "test",
  warnings: ["w"],
});
const needs = { min_sunlit_fraction: 0.8, duration_hours: 72 };

describe("per-site planning requests", () => {
  it("keeps every site's evaluations when merging searches and picks the global best", () => {
    const a = result("a", [candidate("a1", "A", "2026-11-24T00:00:00Z", "PASS", 60)], { candidate_total: 64, pass: 30, fail: 34, indeterminate: 0, returned: 1, not_returned: 63 });
    const b = result("b", [candidate("b1", "B", "2026-11-24T00:15:00Z", "PASS", 70)], { candidate_total: 64, pass: 10, fail: 54, indeterminate: 0, returned: 1, not_returned: 63 });
    const c = result("c", [candidate("c1", "C", "2026-11-24T00:00:00Z", "FAIL", 80)], { candidate_total: 64, pass: 0, fail: 64, indeterminate: 0, returned: 1, not_returned: 63 });
    const merged = mergeSearch([a, b, c], needs);
    expect(merged.coverage.candidate_total).toBe(192);
    expect(merged.coverage.pass).toBe(40);
    // A FAIL near miss is never returned once some site has a PASS.
    expect(merged.candidates.map((x) => x.candidate_id)).toEqual(["b1", "a1"]);
    expect(merged.recommended_candidate_id).toBe("b1");
    expect(merged.coverage.returned).toBe(2);
    expect(merged.coverage.not_returned).toBe(190);
    expect(merged.parts).toEqual(["a", "b", "c"]);
    // Every evaluated start stays available for the grid, not just the picks.
    const rows = mergeSearch([
      { ...a, evaluations: [a.candidates[0], candidate("a2", "A", "2026-11-24T00:15:00Z", "PASS", 50)] },
      { ...b, evaluations: [b.candidates[0]] },
    ], needs).evaluations;
    expect(rows?.map((x) => x.candidate_id)).toEqual(["a1", "a2", "b1"]);
    expect(merged.status).toBe("FEASIBLE");
  });

  it("orders near misses by their largest shortfall, then soft preferences break ties", () => {
    const close = candidate("close", "A", "2026-11-24T00:00:00Z", "FAIL", 55);
    const far = candidate("far", "B", "2026-11-24T00:00:00Z", "FAIL", 20);
    expect(ranked([far, close], needs).map((x) => x.candidate_id)).toEqual(["close", "far"]);
    const soft = candidate("soft", "C", "2026-11-24T00:00:00Z", "PASS", 60, { soft_constraint_states: { continuity: "FAIL" } });
    const clean = candidate("clean", "D", "2026-11-24T00:00:00Z", "PASS", 60);
    expect(ranked([soft, clean], needs)[0].candidate_id).toBe("clean");
  });

  it("recommends only PASS candidates when compare results are merged", () => {
    const merged = mergeCompare([
      result("a", [candidate("a", "A", "2026-11-24T00:00:00Z", "FAIL", 70)], { candidate_total: 1, pass: 0, fail: 1, indeterminate: 0 }),
      result("b", [candidate("b", "B", "2026-11-24T00:00:00Z", "PASS", 61)], { candidate_total: 1, pass: 1, fail: 0, indeterminate: 0 }),
    ], needs);
    expect(merged.candidates).toHaveLength(2);
    expect(merged.recommended_candidate_id).toBe("b");
    expect(merged.apply_allowed).toBe(true);
  });
});

describe("planning site choice", () => {
  it("names custom points by position and evaluates a coordinate once", () => {
    const sites = SITES.filter((s) => !PLANNING_EXCLUDED.has(s.id));
    expect(sites.some((s) => s.id === "connecting-ridge-extension")).toBe(false);
    const choice = { ...initialChoice(sites), customs: [{ id: "custom-1", lat: -88, lon: 10 }, { id: "custom-7", lat: -87, lon: 20 }] };
    const customs = customSites(choice.customs, (i) => `Custom point ${i}`);
    expect(customs.map((s) => s.name)).toEqual(["Custom point 1", "Custom point 2"]);
    const duplicate = { ...customs[0], id: "custom-9", lat: sites[0].lat, lon: sites[0].lon };
    const chosen = chosenSites([...sites, ...customs, duplicate], { ...choice, selected: [...choice.selected, "custom-7", "custom-9"] });
    expect(chosen.map((s) => s.id)).toEqual([sites[0].id, sites[1].id, "custom-7"]);
  });
});

describe("current Sun/Earth state", () => {
  it("uses prepared hourly bins that kept one state, but never mixed bins", () => {
    const hour = (h: number, sun: "V" | "B" | "?", earth: "V" | "B" | "?") => ({
      start_utc: `2026-11-24T0${h}:00:00Z`, end_utc: `2026-11-24T0${h + 1}:00:00Z`, aggregated: true,
      sun_state: sun, earth_state: earth, joint_state: "?" as const,
    });
    const prepared = { timeline: [hour(0, "V", "V"), hour(1, "?", "B")] } as unknown as PointResult;
    const t = Date.parse("2026-11-24T00:37:00Z");
    expect(intervalAt(prepared.timeline, t)).toBeUndefined();
    expect(stateAt(prepared, undefined, t, "sun")).toBe("V");
    expect(stateAt(prepared, undefined, t, "earth")).toBe("V");
    const mixed = Date.parse("2026-11-24T01:10:00Z");
    expect(stateAt(prepared, undefined, mixed, "sun")).toBe("?");
    expect(stateAt(prepared, undefined, mixed, "earth")).toBe("B");
    // An exact five-minute instant still wins inside its own span.
    const instant = { start_utc: "2026-11-24T01:10:00Z", end_utc: "2026-11-24T01:15:00Z", sun_state: "B", earth_state: "B", joint_state: "B" } as const;
    expect(stateAt(prepared, instant, mixed, "sun")).toBe("B");
  });
});
