import { useEffect, useState } from "react";
import { api } from "../mvp/api";
import { responseCache } from "../lib/responseCache";
import type { SkyTable } from "../lib/skyEphemeris";

const load = responseCache<SkyTable>(4);
const ready = new Map<string, { table: SkyTable; expires: number }>();
function getTable(month: string) {
  return load(month, () => api<SkyTable>(`/lunar/point/sky-vectors?at_utc=${encodeURIComponent(month)}`))
    .then((table) => {
      ready.set(month, { table, expires: Date.now()+300000 });
      while (ready.size > 4) ready.delete(ready.keys().next().value!);
      return table;
    });
}

export function useSkyEphemeris(time: number) {
  const date = new Date(time);
  const month = Number.isFinite(time) ? new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1)).toISOString() : "";
  const [stored, setStored] = useState<{ month: string; table: SkyTable }>();
  useEffect(() => {
    if (!month) return;
    let active = true;
    void getTable(month)
      .then((table) => {
        if (!active) return;
        setStored({ month, table });
        // Playback crosses a month without reverting to approximate lighting.
        void getTable(new Date(table.end_utc).toISOString()).catch(() => {});
      })
      .catch(() => { /* The renderer retains its explicitly labelled approximate preview. */ });
    return () => { active = false; };
  }, [month]);
  const cached = ready.get(month);
  return cached && cached.expires > Date.now() ? cached.table : stored?.month === month ? stored.table : undefined;
}
