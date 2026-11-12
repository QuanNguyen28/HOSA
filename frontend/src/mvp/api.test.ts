import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzePoint } from "./api";
import { DEFAULT_MISSION, EXAMPLES, intervalAt, missionRequest, type Interval } from "./contracts";

afterEach(() => vi.unstubAllGlobals());

describe("progressive point transport", () => {
  it("updates an initially empty chart before the final result, without treating a preview as exact", async () => {
    vi.useFakeTimers();
    let polls = 0, previews = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const payload = url.endsWith("/analyses") ? { job_id: "job" }
        : url.endsWith("/preview") ? { evaluation_status: "pending", decision: null,
          timeline: previews++ === 0 ? [] : [{ aggregated: true }],
          timeline_transport: { mode: "aggregated", exact_intervals_ready: false } }
        : url.includes("/result?") ? { evaluation_status: "complete", decision: "PASS" }
        : { status: polls++ === 0 ? "running" : "succeeded", stage: "validation", preview_url: "/preview" };
      return { ok: true, json: async () => payload };
    }));
    const published: Array<{ timeline: unknown[]; interval_url?: string }> = [];
    try {
      const done = analyzePoint(missionRequest(DEFAULT_MISSION, EXAMPLES[0]), new AbortController().signal, vi.fn(), (value) => published.push(value));
      await vi.runAllTimersAsync();
      expect((await done).decision).toBe("PASS");
      expect(published.map((value) => value.timeline.length)).toEqual([0, 1]);
      expect(published.every((value) => value.interval_url === undefined)).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
  it("publishes pending metrics before requesting the bounded final result", async () => {
    const calls: string[] = [];
    const initial = { evaluation_status: "pending", decision: null, metrics_hours: { total_sun_hours: [36, 36] },
      timeline: [], timeline_transport: { mode: "pending", source_intervals: 1_000_000, display_intervals: 0 } };
    const fetcher = vi.fn(async (url: string) => {
      calls.push(url);
      const payload = url.endsWith("/analyses") ? { job_id: "job" }
        : url.endsWith("/preview") ? initial
        : url.includes("/result?") ? { ...initial, evaluation_status: "complete", decision: "FAIL" }
        : { status: "succeeded", stage: "complete", preview_url: "/preview" };
      return { ok: true, json: async () => payload };
    });
    vi.stubGlobal("fetch", fetcher);
    const preview = vi.fn((value: { interval_url?: string }) => {
      expect(value.interval_url).toBeUndefined();
      expect(calls.some((url) => url.includes("/result?"))).toBe(false);
    });
    const result = await analyzePoint(missionRequest(DEFAULT_MISSION, EXAMPLES[0]), new AbortController().signal, vi.fn(), preview);
    expect(preview).toHaveBeenCalledWith(expect.objectContaining({ evaluation_status: "pending", decision: null }));
    expect(calls.at(-1)).toContain("/result?view=display");
    expect(result.decision).toBe("FAIL");
    expect(result.interval_url).toBe("/lunar/point/analyses/job/interval");
  });

  it("delivers an available preview even when background validation then fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: true, json: async () =>
      url.endsWith("/analyses") ? { job_id: "job" }
        : url.endsWith("/preview") ? { evaluation_status: "pending", decision: null }
        : { status: "failed", stage: "failed", preview_url: "/preview", error_code: "VALIDATION_UNAVAILABLE" },
    })));
    const preview = vi.fn();
    await expect(analyzePoint(missionRequest(DEFAULT_MISSION, EXAMPLES[0]), new AbortController().signal, vi.fn(), preview)).rejects.toThrow("VALIDATION_UNAVAILABLE");
    expect(preview).toHaveBeenCalledOnce();
  });

  it("never labels a multi-day average as an exact current interval", () => {
    const row: Interval = { start_utc: "2026-01-01T00:00:00Z", end_utc: "2026-01-08T00:00:00Z",
      sun_state: "V", earth_state: "?", joint_state: "?", aggregated: true };
    expect(intervalAt([row], Date.parse("2026-01-02T00:00:00Z"))).toBeUndefined();
  });
});
