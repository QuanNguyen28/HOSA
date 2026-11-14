import { useCallback, useEffect, useRef, useState } from "react";
import { currentInterval, intervalAt, type Interval, type MissionRequest, type PointResult } from "./contracts";
import { instantTime, startInstantReader, type InstantQuery } from './instantReader';
const HORIZON_NOT_PREPARED = "HORIZON_NOT_PREPARED";

export function errorText(payload: unknown, status: number): string {
  const detail = (payload as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map(
        (x) =>
          `${x.loc?.slice(1).join(".") ?? "Request"}: ${x.msg ?? "Invalid value"}`,
      )
      .join("; ");
  if (detail && typeof detail === "object" && "code" in detail)
    return String(detail.code);
  return `API request failed (${status}).`;
}
export async function api<T>(
  path: string,
  signal?: AbortSignal,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  const response = await fetch("/api" + path, {
    signal,
    ...(body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify(body),
        }),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorText(payload, response.status));
  if (payload === null)
    throw new Error(
      "The API did not return JSON. Check the backend connection.",
    );
  return payload as T;
}
export function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
/** Rough position of each PointAnalysisService stage in a full Analyze run. */
const ANALYSIS_STAGES: [string, number][] = [
  ["queued", .03], ["waiting_for_worker", .05], ["verify_dem", .1], ["cached_horizon", .15],
  ["precomputed_horizon", .15], ["seam_validation", .18], ["horizons_5min", .22], ["indexed_metrics", .3],
  ["cached_physical_series", .3], ["initial_metrics", .36], ["metrics_ready_preparing_details", .45],
  ["horizons_1min", .5], ["hard_requirements", .58], ["confirming_hard_failure_1min", .62],
  ["scientific_validation", .66], ["metrics_and_validation", .7], ["checking_mission_bounds", .75],
  ["refining_horizon_", .8], ["revalidating_", .85], ["soft_preferences", .93], ["commit_artifacts", .97],
  ["cached", .95], ["complete", 1],
];
export function analysisProgress(stage: string): number | undefined {
  return ANALYSIS_STAGES.find(([name]) => name.endsWith("_") ? stage.startsWith(name) : stage === name || stage.startsWith(name + "_"))?.[1];
}
export async function analyzePoint(
  request: MissionRequest,
  signal: AbortSignal,
  progress: (stage: string) => void,
  preview?: (result: PointResult) => void,
  advance?: (fraction: number) => void,
): Promise<PointResult> {
  const job = await api<{ job_id: string }>(
    "/lunar/point/analyses",
    signal,
    request,
  );
  let previewLoaded = false;
  let chartReady = false;
  let polls = 0;
  let reached = 0;
  const intervalUrl = `/lunar/point/analyses/${job.job_id}/interval`;
  for (;;) {
    const state = await api<{
      status: string;
      stage: string;
      error_code?: string;
      result_url?: string;
      preview_url?: string;
    }>(`/lunar/point/analyses/${job.job_id}`, signal);
    if (state.preview_url && (!previewLoaded || !chartReady)) {
      const initial = await api<PointResult>(`/lunar/point/analyses/${job.job_id}/preview`, signal);
      preview?.({ ...initial, interval_url: initial.timeline_transport?.mode === "pending" || initial.timeline_transport?.exact_intervals_ready === false ? undefined : intervalUrl });
      previewLoaded = true;
      chartReady = (initial.timeline?.length ?? 0) > 0;
    }
    reached = Math.max(reached, analysisProgress(state.stage) ?? reached);
    advance?.(reached);
    progress(
      state.stage.startsWith("refining_horizon_") ||
        state.stage.startsWith("revalidating_")
        ? "Completing scientific validation · " +
            state.stage.replaceAll("_", " ")
        : state.stage.replaceAll("_", " "),
    );
    if (state.status === "failed")
      throw new Error(state.error_code ?? "Point analysis failed.");
    if (state.status === "succeeded") {
      const result = await api<PointResult>(
        `/lunar/point/analyses/${job.job_id}/result?view=display`,
        signal,
      );
      return { ...result, interval_url: intervalUrl };
    }
    // Prepared points usually publish within the first few polls. Avoid adding
    // a whole second to a cache hit, then back off for actual long computation.
    polls++;
    await wait(previewLoaded ? 750 : polls < 12 ? 100 : 500, signal);
  }
}
/** Work callbacks: stage text, partial result, and numeric progress (0–1). */
export type OperationWork<T> = (
  signal: AbortSignal,
  progress: (stage: string) => void,
  publish: (value: T) => void,
  advance: (fraction: number) => void,
) => Promise<T>;
export function useOperation<T>(key: string) {
  const [stored, setStored] = useState<{
    key: string;
    data?: T;
    error?: string;
  }>({ key });
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [fraction, setFraction] = useState<number>();
  const active = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  useEffect(() => {
    active.current?.abort();
    sequence.current++;
    setBusy(false);
    setStage("");
    setFraction(undefined);
    return () => {
      active.current?.abort();
    };
  }, [key]);
  const run = useCallback(
    async (work: OperationWork<T>) => {
      active.current?.abort();
      const controller = new AbortController();
      active.current = controller;
      const id = ++sequence.current;
      const live = () => !controller.signal.aborted && id === sequence.current;
      setStored({ key });
      setBusy(true);
      setStage("Starting");
      setFraction(undefined);
      try {
        const data = await work(controller.signal, (v) => {
          if (live()) setStage(v);
        }, (data) => {
          if (live()) setStored({ key, data });
        }, (v) => {
          if (live()) setFraction(Math.max(0, Math.min(1, v)));
        });
        if (live()) setStored({ key, data });
      } catch (e) {
        if (live())
          setStored((previous) => ({
            key,
            data: previous.key === key ? previous.data : undefined,
            error: e instanceof Error ? e.message : "Request failed.",
          }));
      } finally {
        if (id === sequence.current) {
          setBusy(false);
          setFraction(undefined);
        }
      }
    },
    [key],
  );
  /** Stop the running request; anything already published stays visible. */
  const cancel = useCallback(() => {
    active.current?.abort();
    sequence.current++;
    setBusy(false);
    setStage("");
    setFraction(undefined);
  }, []);
  return {
    result: stored.key === key ? stored.data : undefined,
    error: stored.key === key ? stored.error : undefined,
    busy,
    stage,
    fraction,
    run,
    cancel,
  };
}

type Series = { evidence_source: Interval["evidence_source"]; sampling_minutes: number; rows: Interval[] };
const seriesCache = new Map<string, Interval[] | null>();
/**
 * Every nominal five-minute state of the mission for a catalog point, loaded
 * once with the other cached metrics. null: not available for this point
 * (custom coordinates use one computed instant per selected time instead).
 */
function useNominalSeries(request?: MissionRequest) {
  const key = request ? JSON.stringify(request) : "";
  const [stored, setStored] = useState<{ key: string; rows: Interval[] | null }>();
  useEffect(() => {
    if (!key || seriesCache.has(key)) return;
    const controller = new AbortController();
    api<Series>("/lunar/point/instants", controller.signal, JSON.parse(key))
      .then((series) => {
        const rows = series.rows.map((row) => ({ ...row, evidence_source: series.evidence_source, sampling_minutes: series.sampling_minutes }));
        seriesCache.set(key, rows);
        if (seriesCache.size > 24) seriesCache.delete(seriesCache.keys().next().value!);
        setStored({ key, rows });
      })
      .catch((error: Error) => {
        if (controller.signal.aborted) return;
        // Definite answers are remembered; a network failure is retried next time.
        if (["INSTANT_NOT_PREPARED", "SERIES_TOO_LONG"].includes(error.message)) seriesCache.set(key, null);
        setStored({ key, rows: null });
      });
    return () => controller.abort();
  }, [key]);
  return seriesCache.has(key) ? seriesCache.get(key)! : stored?.key === key ? stored.rows : undefined;
}

export function usePointInstant(result: PointResult | undefined, time: number, fallbackRequest?: MissionRequest) {
  const [stored, setStored] = useState<{ key: string; row: Interval }>();
  const [failure, setFailure] = useState<{scope: string; message: string}>();
  const cache = useRef(new Map<string, Interval>());
  const native = result && currentInterval(result, time);
  const url = result?.interval_url;
  const request = result?.request ?? fallbackRequest;
  // An analysed point's refined intervals beat the nominal series.
  const series = useNominalSeries(url ? undefined : fallbackRequest ?? result?.request);
  const fromSeries = series ? intervalAt(series, time) : undefined;
  const scope = JSON.stringify([result?.result_id,url,result?.evaluation_status,request]);
  const tick = request ? instantTime(time,request.start_utc,!!url) : NaN;
  const key = `${scope}|${tick}`;
  const cached = cache.current.get(key) ?? (stored?.key === key ? stored.row : undefined);
  const inWindow = !!request && time >= Date.parse(request.start_utc) && time < Date.parse(request.end_utc);
  const snapshot = useRef<{scope: string; query?: InstantQuery}>({scope});
  snapshot.current = {scope,query:request && inWindow && !native && !fromSeries && !cached && Number.isFinite(tick)
    ? {key,at:tick,request,url} : undefined};
  useEffect(() => {
    return startInstantReader(
      () => snapshot.current.scope===scope ? snapshot.current.query : undefined,
      (query,signal) => api<Interval>(`${query.url ?? '/lunar/point/instant'}?at_utc=${encodeURIComponent(new Date(query.at).toISOString())}`,
        signal,query.url ? undefined : query.request),
      (query,row) => {
        if (!intervalAt([row],query.at)) return;
        cache.current.set(query.key,row);
        if(cache.current.size>64) cache.current.delete(cache.current.keys().next().value!);
        setStored({key:query.key,row});setFailure(undefined);
      },
      error => setFailure({scope,message:error.message}),
    );
  }, [scope]);
  const instant = native ?? fromSeries ?? (inWindow && cached ? intervalAt([cached],time) : undefined);
  const error = !instant && failure?.scope===scope ? failure.message : undefined;
  // A custom point's horizon is still being prepared in the background.
  return {instant,error,loading:inWindow && !instant && (!error || error === HORIZON_NOT_PREPARED)};
}

const preparedMetricCache = new Map<string, PointResult>();
export function usePreparedMetrics(request: MissionRequest | undefined, watchPrepared = false) {
  const key = request ? JSON.stringify(request) : "";
  const [stored, setStored] = useState<{ key: string; result: PointResult }>();
  useEffect(() => {
    if (!key || preparedMetricCache.has(key)) return;
    const controller = new AbortController();
    const load = async () => {
      const body = JSON.parse(key) as MissionRequest;
      const withinPreparedBand = Date.parse(body.start_utc) >= Date.UTC(2000, 0, 1)
        && Date.parse(body.end_utc) <= Date.UTC(2101, 0, 1)
        && Date.parse(body.start_utc) % 86_400_000 === 0
        && Date.parse(body.end_utc) % 86_400_000 === 0;
      while (!controller.signal.aborted) {
        try {
          const result = await api<PointResult>("/lunar/point/metrics", controller.signal, body);
          if (controller.signal.aborted) return;
          preparedMetricCache.set(key, result);
          if (preparedMetricCache.size > 100) preparedMetricCache.delete(preparedMetricCache.keys().next().value!);
          setStored({ key, result });
          return;
        } catch (error) {
          // Named catalog products may be published while this page is open.
          // Arbitrary coordinates/out-of-band requests still use Analyze.
          if (!watchPrepared || !withinPreparedBand || !(error instanceof Error)
              || error.message !== "METRICS_NOT_PREPARED") return;
          await wait(5000, controller.signal);
        }
      }
    };
    void load().catch(() => { /* Aborted on observer or view changes. */ });
    return () => controller.abort();
  }, [key, watchPrepared]);
  return preparedMetricCache.get(key) ?? (stored?.key === key ? stored.result : undefined);
}
export function downloadJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
