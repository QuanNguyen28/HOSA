import { useCallback, useEffect, useRef, useState } from "react";
import { intervalAt, type Interval, type MissionRequest, type PointResult } from "./contracts";

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
export async function analyzePoint(
  request: MissionRequest,
  signal: AbortSignal,
  progress: (stage: string) => void,
  preview?: (result: PointResult) => void,
): Promise<PointResult> {
  const job = await api<{ job_id: string }>(
    "/lunar/point/analyses",
    signal,
    request,
  );
  let previewLoaded = false;
  let chartReady = false;
  let polls = 0;
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
export function useOperation<T>(key: string) {
  const [stored, setStored] = useState<{
    key: string;
    data?: T;
    error?: string;
  }>({ key });
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const active = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  useEffect(() => {
    active.current?.abort();
    sequence.current++;
    setBusy(false);
    setStage("");
    return () => {
      active.current?.abort();
    };
  }, [key]);
  const run = useCallback(
    async (
      work: (signal: AbortSignal, progress: (v: string) => void, publish: (value: T) => void) => Promise<T>,
    ) => {
      active.current?.abort();
      const controller = new AbortController();
      active.current = controller;
      const id = ++sequence.current;
      setStored({ key });
      setBusy(true);
      setStage("Starting");
      try {
        const data = await work(controller.signal, (v) => {
          if (!controller.signal.aborted && id === sequence.current) setStage(v);
        }, (data) => {
          if (!controller.signal.aborted && id === sequence.current) setStored({ key, data });
        });
        if (!controller.signal.aborted && id === sequence.current)
          setStored({ key, data });
      } catch (e) {
        if (!controller.signal.aborted && id === sequence.current)
          setStored((previous) => ({
            key,
            data: previous.key === key ? previous.data : undefined,
            error: e instanceof Error ? e.message : "Request failed.",
          }));
      } finally {
        if (id === sequence.current) setBusy(false);
      }
    },
    [key],
  );
  return {
    result: stored.key === key ? stored.data : undefined,
    error: stored.key === key ? stored.error : undefined,
    busy,
    stage,
    run,
  };
}

export function usePointInstant(result: PointResult | undefined, time: number) {
  const [stored, setStored] = useState<{ key: string; row: Interval }>();
  const cache = useRef(new Map<string, Interval>());
  const native = result && intervalAt(result.timeline, time);
  const url = result?.interval_url;
  const request = result ? JSON.stringify(result.request) : undefined;
  // A refined result may use one-minute intervals; a five-minute request key
  // would keep reusing its first minute and leave the other four minutes wrong.
  const step = url ? 60000 : 300000;
  const tick = Math.floor(time / step) * step;
  const key = `${result?.result_id}|${url}|${result?.evaluation_status}|${tick}`;
  const cached = cache.current.get(key) ?? (stored?.key === key ? stored.row : undefined);
  const inWindow = result && time >= Date.parse(result.request.start_utc) && time < Date.parse(result.request.end_utc);
  useEffect(() => {
    if (!request || native || cached || !inWindow || !Number.isFinite(tick)) return;
    const controller = new AbortController();
    // Scrubbing is coalesced; stale responses never replace the selected instant.
    const timer = setTimeout(() => {
      const query = `?at_utc=${encodeURIComponent(new Date(tick).toISOString())}`;
      void api<Interval>(`${url ?? "/lunar/point/instant"}${query}`, controller.signal, url ? undefined : JSON.parse(request))
        .then((row) => {
          if (!controller.signal.aborted && intervalAt([row], tick)) {
            cache.current.set(key, row);
            if (cache.current.size > 64) cache.current.delete(cache.current.keys().next().value!);
            setStored({ key, row });
          }
        })
        .catch(() => { /* Unknown until exact evidence is available. */ });
    }, 150);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [key, native, cached, url, request, tick, inWindow]);
  return native ?? (inWindow && cached ? intervalAt([cached], time) : undefined);
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
