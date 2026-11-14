import type { Interval, MissionRequest } from './contracts';

export type InstantQuery = { key: string; at: number; request: MissionRequest; url?: string };

/** Sampling must never round the first request outside a half-open mission. */
export function instantTime(time: number, start: string, refined: boolean) {
  const step = refined ? 60000 : 300000;
  return Math.max(Date.parse(start), Math.floor(time/step)*step);
}

/** A moving cursor updates the next query instead of cancelling a debounce forever. */
export function startInstantReader(
  latest: () => InstantQuery | undefined,
  load: (query: InstantQuery, signal: AbortSignal) => Promise<Interval>,
  publish: (query: InstantQuery, row: Interval) => void,
  fail: (error: Error) => void,
) {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout>;
  let stopped = false;
  const run = async () => {
    let delay = 150;
    const query = latest();
    if (query) {
      try {
        const row = await load(query, controller.signal);
        if (!stopped) publish(query, row);
      } catch (error) {
        if (!stopped) fail(error instanceof Error ? error : new Error('Request failed.'));
        delay = 2000;
      }
    }
    if (!stopped) timer = setTimeout(run, delay);
  };
  timer = setTimeout(run, 0);
  return () => { stopped = true; clearTimeout(timer); controller.abort(); };
}
