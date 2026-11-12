import { useMemo, useState } from 'react';
import { SITES, HEIGHTS, DAY, STEP, MAX_MS, buildSeries, fmtDate, type Series } from './model';
import { Seg, SunIcon, EarthIcon } from './ui';

const STRIDE = 7;
export function Finder({ hIdx, onOpen }: { hIdx: number; onOpen: (siteId: string, from: number, days: number) => void }) {
  const [year, setYear] = useState(2027);
  const [len, setLen] = useState(14);
  const [minSun, setMinSun] = useState(30);
  const [minEarth, setMinEarth] = useState(50);
  const start = Date.UTC(year, 0, 1), yEnd = Date.UTC(year + 1, 0, 1), end = Math.min(MAX_MS, yEnd + 31 * DAY);

  const pre = useMemo(() => SITES.map((site) => {
    const se: Series = buildSeries(site, HEIGHTS[hIdx], start, end);
    const sun = new Float64Array(se.n + 1), earth = new Float64Array(se.n + 1);
    for (let i = 0; i < se.n; i++) { sun[i + 1] = sun[i] + se.fSun[i]; earth[i + 1] = earth[i] + (se.earthClear[i] > 0 ? 1 : 0); }
    return { site, sun, earth, n: se.n };
  }), [year, hIdx]);
  const starts = useMemo(() => { const o: number[] = []; for (let t = start; t < yEnd; t += STRIDE * DAY) o.push(t); return o; }, [year]);
  const per = DAY / STEP;
  const cells = useMemo(() => pre.map((p) => starts.map((t) => {
    const a = Math.round((t - start) / STEP), b = Math.min(p.n, a + Math.round(len * per)), n = b - a || 1;
    const sunPct = ((p.sun[b] - p.sun[a]) / n) * 100, earthPct = ((p.earth[b] - p.earth[a]) / n) * 100;
    return { sunPct, earthPct, ok: sunPct >= minSun && earthPct >= minEarth };
  })), [pre, starts, len, minSun, minEarth]);
  const best = cells.map((row, i) => {
    let bi = 0; row.forEach((c, j) => { if (c.ok && !row[bi].ok || (c.ok === row[bi].ok && c.sunPct + c.earthPct > row[bi].sunPct + row[bi].earthPct)) bi = j; });
    return { site: pre[i].site, c: row[bi], t: starts[bi], count: row.filter((c) => c.ok).length };
  }).sort((a, b) => b.count - a.count || b.c.sunPct + b.c.earthPct - (a.c.sunPct + a.c.earthPct));
  const months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  const total = starts.length;

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <h2 className="font-display text-3xl font-semibold">Best dates to land</h2>
        </div>
        <div className="glass flex flex-wrap items-center gap-x-6 gap-y-3 rounded-none px-4 py-3">
          <Seg label="Year" value={year} onChange={setYear} options={[2025, 2026, 2027, 2028, 2029, 2030].map((y) => ({ v: y, label: y }))} />
          <Seg label="Mission length" value={len} onChange={setLen} options={[7, 14, 30].map((d) => ({ v: d, label: `${d}d` }))} />
          <label className="flex items-center gap-2 text-xs text-soft"><SunIcon className="text-sun" />
            <input type="range" min={0} max={100} step={5} value={minSun} onChange={(e) => setMinSun(Number(e.target.value))} aria-label="Minimum sunlight" className="w-28" />
            <span className="w-10 font-mono tabular">≥{minSun}%</span></label>
          <label className="flex items-center gap-2 text-xs text-soft"><EarthIcon className="text-earth" />
            <input type="range" min={0} max={100} step={5} value={minEarth} onChange={(e) => setMinEarth(Number(e.target.value))} aria-label="Minimum Earth visibility" className="w-28" />
            <span className="w-10 font-mono tabular">≥{minEarth}%</span></label>
        </div>
      </div>

      <section aria-label="Start date grid" className="glass mt-6 overflow-x-auto rounded-none p-4">
        <div className="min-w-[760px]">
          <div className="flex"><div className="w-44 shrink-0" />
            <div className="relative h-4 flex-1">
              {months.map((m, i) => <span key={i} className="absolute font-mono text-[10px] text-mute" style={{ left: `${((Date.UTC(year, i, 1) - start) / (yEnd - start)) * 100}%` }}>{m}</span>)}
            </div></div>
          {cells.map((row, i) => (
            <div key={pre[i].site.id} className="mt-1 flex items-center">
              <p className="w-44 shrink-0 truncate pr-3 text-xs text-soft">{pre[i].site.name}</p>
              <div className="flex flex-1 gap-[3px]">
                {row.map((c, j) => (
                  <button key={j} type="button" onClick={() => onOpen(pre[i].site.id, starts[j], len)}
                    title={`${pre[i].site.name} · ${fmtDate(starts[j])} · sun ${c.sunPct.toFixed(0)}% · Earth ${c.earthPct.toFixed(0)}%`}
                    aria-label={`${pre[i].site.name}, from ${fmtDate(starts[j])}: sun ${c.sunPct.toFixed(0)}%, Earth ${c.earthPct.toFixed(0)}%${c.ok ? ', meets limits' : ''}`}
                    className="h-6 flex-1 rounded-none transition hover:scale-y-125 hover:outline-1 hover:outline-ice"
                    style={{ background: c.ok ? `rgba(122,217,154,${0.4 + c.sunPct / 170})` : `rgba(111,133,141,${0.08 + (c.sunPct / 100) * 0.22})` }} />
                ))}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 flex items-center gap-2 font-mono text-[10px] text-mute"><i className="size-2.5 rounded-none bg-mint/70" />meets both limits <i className="ml-3 size-2.5 rounded-none bg-mute/25" />does not</p>
      </section>

      <section aria-label="Best sites" className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {best.slice(0, 4).map((b, k) => (
          <button key={b.site.id} type="button" onClick={() => onOpen(b.site.id, b.t, len)} className="glass group rounded-none p-4 text-left transition hover:border-white/40">
            <div className="flex items-center justify-between"><span className="eyebrow">#{k + 1}</span><span className="font-mono text-[10px] text-ice">{b.count}/{total} weeks</span></div>
            <p className="mt-2 font-display text-lg font-semibold">{b.site.name}</p>
            <p className="mt-0.5 font-mono text-[11px] text-mute">best from {fmtDate(b.t)}</p>
            <div className="mt-3 flex gap-4 text-sm tabular">
              <span className="flex items-center gap-1.5"><SunIcon className="text-sun" />{b.c.sunPct.toFixed(0)}%</span>
              <span className="flex items-center gap-1.5"><EarthIcon className="text-earth" />{b.c.earthPct.toFixed(0)}%</span>
            </div>
          </button>
        ))}
      </section>
    </main>
  );
}
