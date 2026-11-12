import { useCallback, useEffect, useRef, useState } from "react";
import type { MissionRequest, PointResult } from "./contracts";

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
): Promise<T> {
  const response = await fetch("/api" + path, {
    signal,
    ...(body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
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
function wait(ms: number, signal: AbortSignal): Promise<void> {
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
): Promise<PointResult> {
  const job = await api<{ job_id: string }>(
    "/lunar/point/analyses",
    signal,
    request,
  );
  for (;;) {
    const state = await api<{
      status: string;
      stage: string;
      error_code?: string;
      result_url?: string;
    }>(`/lunar/point/analyses/${job.job_id}`, signal);
    progress(state.stage.replaceAll("_", " "));
    if (state.status === "failed")
      throw new Error(state.error_code ?? "Point analysis failed.");
    if (state.status === "succeeded")
      return api<PointResult>(
        `/lunar/point/analyses/${job.job_id}/result`,
        signal,
      );
    await wait(1000, signal);
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
      work: (signal: AbortSignal, progress: (v: string) => void) => Promise<T>,
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
          if (id === sequence.current) setStage(v);
        });
        if (!controller.signal.aborted && id === sequence.current)
          setStored({ key, data });
      } catch (e) {
        if (!controller.signal.aborted && id === sequence.current)
          setStored({
            key,
            error: e instanceof Error ? e.message : "Request failed.",
          });
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
