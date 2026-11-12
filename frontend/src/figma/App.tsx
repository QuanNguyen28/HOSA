import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import {
  SITES, HEIGHTS, HOUR, DAY, STEP, MIN_MS, MAX_MS, buildSeries, metrics, liveState, fmtDate, fmtDur, fmtTime, fmtPos,
} from './model';
import { Logo, SunIcon, EarthIcon, Ring, Seg, StatusPair, SiteRail, TimeDock, LiveBar, Timeline, clamp, coords, type Shared } from './ui';
import { Finder } from './views';
import ChatDock, { ChatPage, useAssistant } from './Chat';
import type { Mode } from './Stage3D';

const Stage3D = lazy(() => import('./Stage3D'));
type View = 'explore' | 'compare' | 'dates' | 'chat';
const TABS: [View, string][] = [['explore', 'Explore'], ['compare', 'Compare'], ['dates', 'Best dates'], ['chat', 'Assistant']];

function readParams() {
  const p = new URLSearchParams(window.location.search);
  const parse = (s: string | null, d: number) => { const v = s ? Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(s) ? s + 'T00:00:00Z' : s) : NaN; return Number.isNaN(v) ? d : v; };
  const from = clamp(parse(p.get('from'), Date.UTC(2027, 0, 1)), MIN_MS, MAX_MS - DAY);
  const to = clamp(parse(p.get('to'), from + 29 * DAY) + DAY, from + DAY, MAX_MS);
  const h = HEIGHTS.indexOf(Number(p.get('h')));
  const v = p.get('view');
  const view: View = TABS.some(([t]) => t === v) ? (v as View) : 'explore';
  return { from, to, t: clamp(parse(p.get('t'), from), from, to), site: SITES.find((s) => s.id === p.get('site'))?.id ?? 'connecting-ridge', h: h < 0 ? 0 : h, view };
}

export default function App() {
  const init = useMemo(readParams, []);
  const [view, setView] = useState<View>(init.view);
  const [siteId, setSiteId] = useState(init.site);
  const [startMs, setStart] = useState(init.from);
  const [endMs, setEnd] = useState(init.to);
  const [timeMs, setTime] = useState(init.t);
  const [hIdx, setH] = useState(init.h);
  const [dark, setDark] = useState(0);
  const [margin, setMargin] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(24);
  const [compare, setCompare] = useState(['connecting-ridge', 'shackleton-rim', 'malapert-massif']);
  const s: Shared = { startMs, endMs, timeMs, playing, speed, dark, margin, hIdx };

  useEffect(() => {
    const p = new URLSearchParams();
    if (view !== 'explore') p.set('view', view);
    p.set('site', siteId); p.set('from', fmtDate(startMs)); p.set('to', fmtDate(endMs - DAY));
    p.set('t', new Date(timeMs).toISOString().slice(0, 16) + 'Z'); p.set('h', String(HEIGHTS[hIdx]));
    if (view === 'compare') p.set('cmp', compare.join(','));
    const id = window.setTimeout(() => window.history.replaceState(null, '', '?' + p.toString()), playing ? 400 : 0);
    return () => clearTimeout(id);
  }, [view, siteId, startMs, endMs, timeMs, hIdx, compare, playing]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000); last = now;
      setTime((t) => { const n = t + dt * speed * HOUR; if (n >= endMs) { setPlaying(false); return endMs; } return n; });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, endMs]);

  const setRange = (a: number, b: number) => {
    const st = clamp(Math.round(a / STEP) * STEP, MIN_MS, MAX_MS - DAY), e = clamp(Math.round(b / STEP) * STEP, st + DAY, MAX_MS);
    setStart(st); setEnd(e); setTime((t) => clamp(t, st, e));
  };
  const ctl = { setRange, setTime, setPlaying, setSpeed };
  const go = (v: View) => { setView(v); setPlaying(false); window.scrollTo(0, 0); };

  const assistant = useAssistant({
    s, siteId,
    onSite: (id) => { setSiteId(id); setView('explore'); },
    onCompare: (ids) => { setCompare(ids); go('compare'); },
    onRange: (from, days) => { setRange(from, from + days * DAY); setTime(from); setView('explore'); },
  });

  return (
    <div className="min-h-svh bg-ink">
      <header className="sticky top-0 z-40 border-b border-line bg-ink">
        <div className="flex h-14 items-center gap-4 px-4 lg:px-6">
          <button type="button" onClick={() => go('explore')} className="flex items-center gap-3" aria-label="LunarSight, explore">
            <Logo size={30} />
            <span className="font-display text-[15px] font-bold tracking-[0.12em]">LunarSight</span>
          </button>
          <p className="flex items-center gap-2 font-display text-[15px] font-semibold tracking-[0.06em] text-mute max-md:hidden">
            <span aria-hidden>›</span><span>South Pole</span><span aria-hidden>›</span><span className="text-white">{TABS.find(([v]) => v === view)![1]}</span>
          </p>
          <nav aria-label="Views" className="ml-auto flex h-full items-stretch">
            {TABS.map(([v, l]) => (
              <button key={v} type="button" aria-current={view === v ? 'page' : undefined} onClick={() => go(v)}
                className={`relative px-3 font-display text-[13px] font-semibold tracking-[0.14em] uppercase transition sm:px-5 ${view === v ? 'text-white' : 'text-mute hover:text-white'}`}>
                {l}{view === v && <span className="absolute inset-x-3 bottom-0 h-[3px] bg-white sm:inset-x-5" />}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {view === 'explore' && <Explore s={s} siteId={siteId} onSite={setSiteId} ctl={ctl} setH={setH} initialSurface={new URLSearchParams(window.location.search).has('site')} />}
      {view === 'compare' && <Compare s={s} ids={compare} setIds={setCompare} ctl={ctl} setH={setH} onOpen={(id) => { setSiteId(id); go('explore'); }} />}
      {view === 'chat' && <ChatPage a={assistant} />}
      <ChatDock a={assistant} hidden={view === 'chat'} />
      {view === 'dates' && <Finder hIdx={hIdx} onOpen={(id, from, days) => { setSiteId(id); setRange(from, from + days * DAY); setTime(from); go('explore'); }} />}
    </div>
  );
}

type Ctl = ReturnType<typeof Object>;
function StageFallback() {
  return <div className="absolute inset-0 grid place-items-center font-mono text-[11px] tracking-widest text-mute">LOADING MOON…</div>;
}

/* ---------- Explore ---------- */
function Bar({ label, v, color, icon }: { label: string; v: number; color: string; icon?: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center justify-between text-[13px]"><span className="flex items-center gap-2 text-soft">{icon}{label}</span><span className="font-display text-lg font-semibold tabular">{v.toFixed(0)}%</span></div>
      <div className="mt-1.5 h-[3px] bg-line"><div className="h-full" style={{ width: `${v}%`, background: color }} /></div>
    </div>
  );
}

function Explore({ s, siteId, onSite, ctl, setH, initialSurface }: { s: Shared; siteId: string; onSite: (id: string) => void; ctl: any; setH: (n: number) => void; initialSurface: boolean }) {
  const [mode, setMode] = useState<Mode>(initialSurface ? 'surface' : 'pole');
  const [tab, setTab] = useState<'info' | 'sites'>('info');
  const [all, setAll] = useState(false);
  const site = SITES.find((x) => x.id === siteId)!;
  const series = useMemo(() => buildSeries(site, HEIGHTS[s.hIdx], s.startMs, s.endMs), [site, s.hIdx, s.startMs, s.endMs]);
  const m = useMemo(() => metrics(series, s.dark, s.margin), [series, s.dark, s.margin]);
  const wins = all ? m.windows : m.windows.slice(0, 3);
  const parse = (v: string) => Date.parse(v + 'T00:00:00Z');
  const inp = 'w-full border border-line bg-ink px-2 py-1.5 font-mono text-xs tabular text-soft';
  const dl = () => {
    const iso = (t: number) => new Date(t).toISOString().slice(0, 16) + 'Z';
    const rows = ['site,observer_height_m,start_utc,end_utc,duration_h', ...m.windows.map((w) => [site.id, HEIGHTS[s.hIdx], iso(w.startMs), iso(w.endMs), w.hours.toFixed(2)].join(','))];
    const url = URL.createObjectURL(new Blob([rows.join('\n') + '\n'], { type: 'text/csv' }));
    const a = document.createElement('a'); a.href = url; a.download = `${site.id}-${fmtDate(s.startMs)}-to-${fmtDate(s.endMs - DAY)}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div className="flex h-[calc(100svh-3.5rem)] min-h-[640px] flex-col lg:flex-row">
      <aside className="flex max-h-[50%] w-full shrink-0 flex-col border-b border-line bg-panel lg:max-h-none lg:w-[340px] lg:border-r lg:border-b-0">
        <div className="flex border-b border-line" role="tablist">
          {(['info', 'sites'] as const).map((t) => (
            <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`px-5 py-3 font-display text-[13px] font-semibold tracking-[0.12em] uppercase ${tab === t ? 'bg-ink text-white shadow-[inset_0_2px_0_#fff]' : 'text-mute hover:text-white'}`}>{t === 'info' ? 'Site' : `All sites`}</button>
          ))}
        </div>
        {tab === 'info' ? (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="border-b border-line p-5">
              <h2 className="text-[26px] leading-none font-bold">{site.name}</h2>
              <p className="mt-2 font-mono text-xs text-mute tabular">{coords(site.lat, site.lon, 2)}</p>
            </div>
            <div className="space-y-3 border-b border-line p-5">
              <p className="eyebrow">Right now</p>
              <StatusPair siteId={siteId} timeMs={s.timeMs} h={HEIGHTS[s.hIdx]} />
            </div>
            <div className="space-y-5 border-b border-line p-5">
              <div className="grid grid-cols-2 gap-3">
                <label className="block"><span className="eyebrow">From</span>
                  <input type="date" className={`${inp} mt-1`} min={fmtDate(MIN_MS)} max={fmtDate(MAX_MS - DAY)} value={fmtDate(s.startMs)} onChange={(e) => { const n = parse(e.target.value); if (!Number.isNaN(n)) ctl.setRange(n, Math.max(s.endMs, n + DAY)); }} /></label>
                <label className="block"><span className="eyebrow">To</span>
                  <input type="date" className={`${inp} mt-1`} min={fmtDate(MIN_MS)} max={fmtDate(MAX_MS - DAY)} value={fmtDate(s.endMs - DAY)} onChange={(e) => { const n = parse(e.target.value); if (!Number.isNaN(n)) ctl.setRange(Math.min(s.startMs, n), n + DAY); }} /></label>
              </div>
              <Bar label="Sunlight" v={m.sunMeanPct} color="#ffc53d" icon={<SunIcon size={14} className="text-sun" />} />
              <Bar label="Earth in view" v={m.earthPct} color="#5ab4ff" icon={<EarthIcon size={14} className="text-earth" />} />
              <Bar label="Both at once" v={m.bothPct} color="#7ad99a" />
              <div className="flex items-center justify-between text-[13px]"><span className="text-soft">Longest dark</span><span className="font-display text-lg font-semibold tabular">{fmtDur(m.longestDark)}</span></div>
            </div>
            <div className="border-b border-line p-5">
              <p className="eyebrow mb-3">Viewer height</p>
              <Seg label="Observer height" value={s.hIdx} onChange={setH} options={HEIGHTS.map((h, i) => ({ v: i, label: i === 0 ? 'Lander' : `${h} m` }))} />
            </div>
            <div className="p-5">
              <div className="flex items-center justify-between"><p className="eyebrow">Best times</p>
                {m.windows.length > 0 && <button type="button" onClick={dl} className="text-xs text-mute underline underline-offset-2 hover:text-white">Download CSV</button>}</div>
              {m.windows.length === 0 ? <p className="mt-3 text-sm text-mute">Sun and Earth are never both visible in these dates.</p> : (
                <ul className="mt-2">
                  {wins.map((w) => (
                    <li key={w.startMs} className="border-t border-line first:border-0">
                      <button type="button" onClick={() => ctl.setTime(w.startMs)} className="flex w-full items-center justify-between py-2.5 text-left hover:text-white">
                        <span className="text-sm text-soft tabular">{new Date(w.startMs).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })}</span>
                        <span className="font-display text-base font-semibold tabular">{fmtDur(w.hours)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {m.windows.length > 3 && <button type="button" onClick={() => setAll(!all)} className="mt-1 text-xs text-mute underline underline-offset-2 hover:text-white">{all ? 'Show fewer' : `Show all ${m.windows.length}`}</button>}
            </div>
          </div>
        ) : (
          <SiteRail siteId={siteId} onSite={(id) => { onSite(id); setTab('info'); }} timeMs={s.timeMs} className="min-h-0 flex-1 !border-0 !bg-transparent" />
        )}
      </aside>

      <div className="relative min-h-[320px] flex-1">
        <Suspense fallback={<StageFallback />}>
          <Stage3D className="absolute inset-0" mode={mode} siteId={siteId} timeMs={s.timeMs} heightM={HEIGHTS[s.hIdx]} onSelect={(id) => { onSite(id); setTab('info'); }} />
        </Suspense>
        <div className="absolute top-4 left-1/2 -translate-x-1/2">
          <Seg label="View" value={mode} onChange={setMode} options={[{ v: 'orbit', label: 'Moon' }, { v: 'pole', label: 'Pole' }, { v: 'surface', label: 'Ground' }]} />
        </div>
        <LiveBar s={s} {...ctl}>
          <Timeline rows={[{ label: site.name, series }]} s={s} setTime={ctl.setTime} />
        </LiveBar>
      </div>
    </div>
  );
}

/* ---------- Compare ---------- */
function Compare({ s, ids, setIds, ctl, setH, onOpen }: { s: Shared; ids: string[]; setIds: (v: string[]) => void; ctl: any; setH: (n: number) => void; onOpen: (id: string) => void }) {
  const sites = ids.map((i) => SITES.find((x) => x.id === i)!).filter(Boolean);
  const data = useMemo(() => sites.map((x) => ({ site: x, series: buildSeries(x, HEIGHTS[s.hIdx], s.startMs, s.endMs) })), [ids, s.hIdx, s.startMs, s.endMs]);
  const ms = useMemo(() => data.map((d) => metrics(d.series, s.dark, s.margin)), [data, s.dark, s.margin]);
  const set = (i: number, v: string) => { const n = [...ids]; if (v) n[i] = v; else n.splice(i, 1); setIds([...new Set(n)]); };
  const top = (f: (m: ReturnType<typeof metrics>) => number, low = false) => { if (ms.length < 2) return -1; const v = ms.map(f); const b = low ? Math.min(...v) : Math.max(...v); return v.indexOf(b); };
  const bestBoth = top((m) => m.bothPct), bestSun = top((m) => m.sunMeanPct), bestEarth = top((m) => m.earthPct);
  const bestDark = top((m) => m.longestDark, true), bestBlack = top((m) => m.longestBlackout, true);
  return (
    <main className="mx-auto max-w-[1400px] space-y-4 px-4 py-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><h2 className="font-display text-3xl font-semibold">Compare sites</h2></div>
        <Seg label="Observer height" value={s.hIdx} onChange={setH} options={HEIGHTS.map((h, i) => ({ v: i, label: i === 0 ? 'Lander' : `${h} m` }))} />
      </div>
      <TimeDock s={s} {...ctl} />
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: Math.min(3, sites.length + 1) }, (_, i) => {
          const d = data[i], m = ms[i];
          return (
            <section key={i} className={`glass rounded-none p-5 ${d && bestBoth === i ? 'border-mint/40 ' : ''}`} aria-label={`Site ${i + 1}`}>
              <select aria-label={`Site ${i + 1}`} value={ids[i] ?? ''} onChange={(e) => set(i, e.target.value)} className="w-full rounded-none border border-line bg-ink/70 px-3 py-2 font-display text-sm font-semibold">
                {i > 0 && <option value="">— Add a site —</option>}{SITES.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
              {d && m && (<>
                <p className="mt-2 flex items-center justify-between font-mono text-[11px] text-mute tabular"><span>{fmtPos(d.site, 1)}</span>{bestBoth === i && <span className="text-mint">★ Best</span>}</p>
                <div className="mt-5 space-y-4">
                  <Bar label="Sunlight" v={m.sunMeanPct} color="#ffc53d" icon={<SunIcon size={14} className="text-sun" />} />
                  <Bar label="Earth in view" v={m.earthPct} color="#5ab4ff" icon={<EarthIcon size={14} className="text-earth" />} />
                  <Bar label="Both at once" v={m.bothPct} color="#7ad99a" />
                </div>
                <dl className="mt-5 space-y-2 text-sm">
                  {[['Longest dark', fmtDur(m.longestDark), bestDark === i], ['Longest blackout', fmtDur(m.longestBlackout), bestBlack === i]].map(([k, v, b]) => (
                    <div key={k as string} className="flex items-center justify-between border-t border-line pt-2"><dt className="text-mute">{k as string}</dt><dd className={`font-mono text-xs tabular ${b ? 'text-white' : ''}`}>{v as string}{b ? ' ★' : ''}</dd></div>
                  ))}
                </dl>
                <button type="button" onClick={() => onOpen(d.site.id)} className="mt-4 w-full rounded-none border border-line py-2 font-mono text-[10px] tracking-[0.16em] text-soft uppercase hover:border-white/40 hover:text-white">View on Moon →</button>
              </>)}
            </section>
          );
        })}
      </div>
      <section aria-label="Timelines" className="glass rounded-none p-4">
        <Timeline rows={data.map((d) => ({ label: d.site.name, series: d.series }))} s={s} setTime={ctl.setTime} />
      </section>
    </main>
  );
}
