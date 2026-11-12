import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { useSiteAnalysis } from '../hooks/useSiteAnalysis';
import {
  SITES, GROUPS, GROUP_ORDER, SPEEDS, HOUR, DAY, STEP, MIN_MS, MAX_MS, liveState, fmtDate, fmtTime, fmtLat, fmtLon, type Series,
} from './model';

export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export type Shared = { startMs: number; endMs: number; timeMs: number; playing: boolean; speed: number; dark: number; margin: number; hIdx: number };
export type Ctl = {
  setRange: (a: number, b: number) => void; setTime: (f: number | ((t: number) => number)) => void;
  setPlaying: (p: boolean) => void; setSpeed: (n: number) => void;
};

/* ---------- icons ---------- */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="none" stroke="#fff" strokeWidth="1.2" />
      <path d="M20.5 9.2a7.8 7.8 0 1 0 2.3 11.4A6.3 6.3 0 0 1 20.5 9.2Z" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="22.5" cy="9.5" r="1.6" fill="#ffc53d" />
    </svg>
  );
}
export function SunIcon({ className = '', size = 16 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className={className}>
      <circle cx="8" cy="8" r="3.2" fill="currentColor" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => <line key={a} x1="8" y1="1.2" x2="8" y2="3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" transform={`rotate(${a} 8 8)`} />)}
    </svg>
  );
}
export function EarthIcon({ className = '', size = 16 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className={className}>
      <circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <ellipse cx="8" cy="8" rx="2.6" ry="6.2" fill="none" stroke="currentColor" strokeWidth="1.1" />
      <line x1="1.8" y1="8" x2="14.2" y2="8" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  );
}
export const PlayIcon = ({ playing }: { playing: boolean }) => playing
  ? <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect x="2" y="1.5" width="3.4" height="11" rx="1" fill="currentColor" /><rect x="8.6" y="1.5" width="3.4" height="11" rx="1" fill="currentColor" /></svg>
  : <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 1.8v10.4a.6.6 0 0 0 .9.5l8.3-5.2a.6.6 0 0 0 0-1L3.9 1.3a.6.6 0 0 0-.9.5Z" fill="currentColor" /></svg>;

/* ---------- ring gauge ---------- */
export function Ring({ value, label, color, icon, size = 112, best, suffix = '%' }: { value: number; label: string; color: string; icon?: ReactNode; size?: number; best?: boolean; suffix?: string }) {
  const r = size / 2 - 8, c = 2 * Math.PI * r, v = clamp(value, 0, 100);
  return (
    <div className="flex flex-col items-center gap-2" role="img" aria-label={`${label}: ${value.toFixed(0)}${suffix}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#14232a" strokeWidth="4" />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} style={{ transition: 'stroke-dashoffset .6s cubic-bezier(.2,.8,.2,1)', filter: 'none' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-2xl font-semibold tabular">{value.toFixed(0)}<span className="text-sm text-mute">{suffix}</span></span>
        </div>
        {best && <span className="absolute -top-2 left-1/2 -translate-x-1/2 bg-white px-1.5 font-display text-[10px] font-bold tracking-widest text-ink">TOP</span>}
      </div>
      <span className="flex items-center gap-1.5 text-xs text-soft">{icon}{label}</span>
    </div>
  );
}

export function Seg<T extends string | number>({ value, options, onChange, label }: { value: T; options: { v: T; label: ReactNode }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex border border-line bg-ink/85">
      {options.map((o) => (
        <button key={String(o.v)} type="button" role="radio" aria-checked={o.v === value} onClick={() => onChange(o.v)}
          className={`px-4 py-2 font-display text-[12px] font-semibold tracking-[0.14em] whitespace-nowrap uppercase transition ${o.v === value ? 'bg-white text-ink' : 'text-soft hover:text-white'}`}>{o.label}</button>
      ))}
    </div>
  );
}

/* ---------- live status chips ---------- */
export function StatusPair({ siteId, timeMs, h = 2 }: { siteId: string; timeMs: number; h?: number }) {
  const site = SITES.find((s) => s.id === siteId)!;
  const l = liveState(site, timeMs, h);
  const analysisSiteId = siteId === 'connecting-ridge'
    ? 'Site01_P1'
    : siteId === 'shackleton-rim'
      ? 'Site04_P1'
      : null;
  const { analysis } = useSiteAnalysis(analysisSiteId, new Date(timeMs));
  const exact = analysis?.availability === 'AVAILABLE' ? analysis.instant : undefined;
  const clearance = (value: number | null | undefined) => value == null
    ? 'unknown clearance'
    : `${value >= 0 ? '+' : ''}${value.toFixed(2)}° clearance`;
  const Chip = ({ icon, on, title, sub }: { icon: ReactNode; on: boolean; title: string; sub: string }) => (
    <div className={`flex flex-1 items-center gap-3 rounded-none border px-3 py-2.5 ${on ? 'border-mint/30 bg-mint/[0.06]' : 'border-rose/25 bg-rose/[0.05]'}`}>
      <span className={on ? 'text-mint' : 'text-rose'}>{icon}</span>
      <div className="min-w-0">
        <p className={`font-display text-sm font-semibold ${on ? 'text-mint' : 'text-rose'}`}>{title}</p>
        <p className="font-mono text-[10px] text-mute tabular">{sub}</p>
      </div>
    </div>
  );
  return (
    <div className="flex gap-2">
      <Chip
        icon={<SunIcon size={20} />}
        on={exact ? exact.sun.state === 'V' : l.sun > 0}
        title={exact ? exact.sun.state === 'V' ? 'Sun lit' : exact.sun.state === 'B' ? 'Sun hidden' : 'Sun unknown' : l.sun >= 1 ? 'Sun lit' : l.sun > 0 ? `Sun ${Math.round(l.sun * 100)}%` : 'Sun hidden'}
        sub={exact ? clearance(exact.sun.clearance_deg) : clearance(l.sunClear)}
      />
      <Chip
        icon={<EarthIcon size={20} />}
        on={exact ? exact.earth.state === 'V' : l.earthUp}
        title={exact ? exact.earth.state === 'V' ? 'Earth link' : exact.earth.state === 'B' ? 'Earth blocked' : 'Earth unknown' : l.earthUp ? 'Earth link' : 'Earth blocked'}
        sub={exact ? clearance(exact.earth.clearance_deg) : clearance(l.earthClear)}
      />
    </div>
  );
}

/* ---------- site rail ---------- */
export function SiteRail({ siteId, onSite, timeMs, className = '' }: { siteId: string; onSite: (id: string) => void; timeMs: number; className?: string }) {
  return (
    <div className={`glass flex flex-col rounded-none ${className}`}>
      <p className="eyebrow px-4 pt-3.5 pb-2">Sites · {SITES.length}</p>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {GROUP_ORDER.map((g) => (
          <div key={g} className="mb-2">
            <p className="px-2 pt-2 pb-1 font-mono text-[9px] tracking-[0.14em] text-mute/80 uppercase">{GROUPS[g]}</p>
            {SITES.filter((s) => s.group === g).map((s) => {
              const l = liveState(s, timeMs, 2);
              const c = l.sun > 0 && l.earthUp ? 'bg-mint' : l.sun > 0 || l.earthUp ? 'bg-amber' : 'bg-mute/60';
              const on = s.id === siteId;
              return (
                <button key={s.id} type="button" onClick={() => onSite(s.id)} aria-pressed={on}
                  className={`group flex w-full items-center gap-2.5 rounded-none px-2.5 py-2 text-left transition ${on ? 'bg-white/[0.07] ' : 'hover:bg-white/[0.04]'}`}>
                  <span className={`size-2 shrink-0 rounded-full ${c} ${s.kind === 'approx' ? 'ring-1 ring-offset-1 ring-offset-panel ring-soft/50' : ''}`} />
                  <span className={`flex-1 truncate text-[13px] ${on ? 'font-semibold text-white' : 'text-soft group-hover:text-white'}`}>{s.name}</span>
                  <span className="flex gap-1 text-[10px]"><SunIcon size={11} className={l.sun > 0 ? 'text-sun' : 'text-mute/40'} /><EarthIcon size={11} className={l.earthUp ? 'text-earth' : 'text-mute/40'} /></span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <p className="flex items-center gap-3 border-t border-line px-4 py-2.5 text-[10px] text-mute">
        <span className="flex items-center gap-1"><i className="size-1.5 rounded-full bg-mint" />Sun + Earth</span>
        <span className="flex items-center gap-1"><i className="size-1.5 rounded-full bg-amber" />One</span>
        <span className="flex items-center gap-1"><i className="size-1.5 rounded-full bg-mute/60" />None</span>
      </p>
    </div>
  );
}

/* ---------- time dock ---------- */
export function TimeDock({ s, setRange, setTime, setPlaying, setSpeed, className = '' }: { s: Shared; className?: string } & Ctl) {
  const ids = { a: useId(), b: useId(), sc: useId(), sp: useId() };
  const parse = (v: string) => Date.parse(v + 'T00:00:00Z');
  const minD = fmtDate(MIN_MS), maxD = fmtDate(MAX_MS - DAY);
  const inp = 'rounded-none border border-line bg-ink/70 px-2 py-1 font-mono text-[11px] tabular text-soft';
  return (
    <section aria-label="Time" className={`glass flex flex-wrap items-center gap-x-5 gap-y-3 rounded-none px-4 py-3 ${className}`}>
      <div className="min-w-[170px]">
        <p className="eyebrow">Simulation · UTC</p>
        <p className="font-mono text-sm font-medium tabular text-white">{fmtTime(s.timeMs).replace(' UTC', '')}</p>
      </div>
      <button type="button" aria-pressed={s.playing} aria-label={s.playing ? 'Pause' : 'Play'}
        onClick={() => { if (!s.playing && s.timeMs >= s.endMs) setTime(s.startMs); setPlaying(!s.playing); }}
        className="flex size-10 items-center justify-center rounded-none border border-white/40 bg-white/[0.07] text-ice-100 hover:bg-white/15"><PlayIcon playing={s.playing} /></button>
      <div className="flex min-w-[220px] flex-1 flex-col gap-1">
        <label htmlFor={ids.sc} className="sr-only">Time within the selected range</label>
        <input id={ids.sc} type="range" min={s.startMs} max={s.endMs} step={STEP} value={s.timeMs} onChange={(e) => setTime(Number(e.target.value))} className="w-full" />
        <div className="flex items-center justify-between gap-2 font-mono text-[10px] text-mute">
          <label className="flex items-center gap-1.5"><span className="sr-only">From</span>
            <input id={ids.a} type="date" min={minD} max={maxD} value={fmtDate(s.startMs)} className={inp}
              onChange={(e) => { const n = parse(e.target.value); if (!Number.isNaN(n)) setRange(n, Math.max(s.endMs, n + DAY)); }} /></label>
          <span aria-hidden>→</span>
          <label className="flex items-center gap-1.5"><span className="sr-only">To</span>
            <input id={ids.b} type="date" min={minD} max={maxD} value={fmtDate(s.endMs - DAY)} className={inp}
              onChange={(e) => { const n = parse(e.target.value); if (!Number.isNaN(n)) setRange(Math.min(s.startMs, n), n + DAY); }} /></label>
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <button type="button" aria-label="Back one hour" onClick={() => setTime(Math.max(s.startMs, s.timeMs - HOUR))} className="rounded-none border border-line px-2 py-1.5 font-mono text-[11px] text-soft hover:border-white/40">−1h</button>
        <button type="button" aria-label="Forward one hour" onClick={() => setTime(Math.min(s.endMs, s.timeMs + HOUR))} className="rounded-none border border-line px-2 py-1.5 font-mono text-[11px] text-soft hover:border-white/40">+1h</button>
        <label htmlFor={ids.sp} className="sr-only">Speed</label>
        <select id={ids.sp} value={s.speed} onChange={(e) => setSpeed(Number(e.target.value))} className="rounded-none border border-line bg-ink/70 px-2 py-1.5 font-mono text-[11px] text-soft">
          {SPEEDS.map((v) => <option key={v} value={v}>{v >= 24 ? `${v / 24}d/s` : `${v}h/s`}</option>)}
        </select>
        <button type="button" aria-label="Back to start" onClick={() => { setPlaying(false); setTime(s.startMs); }} className="flex size-8 items-center justify-center rounded-none border border-line text-soft hover:border-white/40">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M3 8a5 5 0 1 0 1.6-3.7M3 2v3h3" /></svg>
        </button>
      </div>
    </section>
  );
}

/* ---------- timeline ---------- */
export function Timeline({ rows, s, setTime }: { rows: { label: string; series: Series }[]; s: Shared; setTime: Ctl['setTime'] }) {
  const wrap = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  const [w, setW] = useState(900);
  useEffect(() => {
    const el = wrap.current; if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth)); ro.observe(el); setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const labelW = 34, cw = Math.max(100, w - labelW);
  const BAR = 14, BG = 17, HDR = rows.length > 1 ? 20 : 0, ROW = BG * 3, GAP = 14;
  const rowH = HDR + ROW + GAP, ch = rows.length * (HDR + ROW) + (rows.length - 1) * GAP;
  const span = s.endMs - s.startMs;

  useEffect(() => {
    const c = cv.current; if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(cw * dpr); c.height = Math.round(ch * dpr);
    const g = c.getContext('2d')!; g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height);
    const W = Math.round(cw * dpr), bar = BAR * dpr;
    const sun = '#ffc53d', earth = '#5ab4ff', mint = '#7ad99a';
    rows.forEach((r, ri) => {
      const top = (ri * rowH + HDR) * dpr;
      g.fillStyle = '#0d181c';
      for (let k = 0; k < 3; k++) { g.beginPath(); g.roundRect(0, top + k * BG * dpr, W, bar, 3 * dpr); g.fill(); }
      const se = r.series; if (!se.n) return;
      const A = [new Float32Array(W), new Float32Array(W), new Float32Array(W)];
      for (let px = 0; px < W; px++) {
        const a = Math.floor((px * se.n) / W), b = Math.max(a + 1, Math.floor(((px + 1) * se.n) / W));
        let ss = 0, ee = 0, bb = 0, n = 0;
        for (let i = a; i < b && i < se.n; i++) { n++; ss += se.fSun[i]; const ok = se.earthClear[i] > s.margin; if (ok) ee++; if (ok && se.fSun[i] > s.dark) bb++; }
        n = n || 1; A[0][px] = ss / n; A[1][px] = ee / n; A[2][px] = bb / n;
      }
      [sun, earth, mint].forEach((col, k) => {
        g.fillStyle = col; const base = top + k * BG * dpr + bar;
        for (let px = 0; px < W; px++) { const h = A[k][px] * bar; if (h > 0.2) g.fillRect(px, base - h, 1, h); }
      });
    });
  }, [rows, cw, ch, s.dark, s.margin, rowH, HDR]);

  const ticks = useMemo(() => {
    const n = Math.max(2, Math.floor(cw / 80)), stepD = Math.max(1, Math.ceil(span / DAY / n)), out: number[] = [];
    for (let t = Math.ceil(s.startMs / DAY) * DAY; t <= s.endMs; t += stepD * DAY) { const x = ((t - s.startMs) / span) * cw; if (x <= cw - 24) out.push(t); }
    return out;
  }, [s.startMs, s.endMs, cw, span]);
  const cx = ((s.timeMs - s.startMs) / span) * cw;
  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setTime(Math.round((s.startMs + (clamp(e.clientX - r.left, 0, cw) / cw) * span) / STEP) * STEP);
  };
  const icons = [<SunIcon key="s" size={14} className="text-sun" />, <EarthIcon key="e" size={14} className="text-earth" />, <span key="b" className="size-2 rounded-full bg-mint" />];
  return (
    <div ref={wrap} className="flex w-full">
      <div className="shrink-0" style={{ width: labelW }}>
        {rows.map((r, ri) => (
          <div key={ri} style={{ height: HDR + ROW, marginTop: ri ? GAP : 0 }}>
            {HDR > 0 && <div style={{ height: HDR }} />}
            {icons.map((ic, k) => <div key={k} className="flex items-center" style={{ height: BG }}>{ic}</div>)}
          </div>
        ))}
      </div>
      <div className="relative min-w-0 flex-1 cursor-pointer" onClick={seek} style={{ height: ch + 22 }}>
        {rows.length > 1 && rows.map((r, ri) => <p key={ri} className="pointer-events-none absolute font-display text-xs font-semibold text-white" style={{ top: ri * rowH, left: 0 }}>{r.label}</p>)}
        <canvas ref={cv} style={{ width: cw, height: ch }} role="img" aria-label="Sun, Earth and both across the selected dates" />
        <div className="pointer-events-none absolute top-0 w-px bg-ice " style={{ left: cx, height: ch }} />
        <svg width={cw} height={22} className="absolute" style={{ top: ch + 2 }} aria-hidden="true">
          {ticks.map((t) => { const x = ((t - s.startMs) / span) * cw; return <text key={t} x={x} y={14} textAnchor="middle" className="fill-mute font-mono text-[10px]">{new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })}</text>; })}
        </svg>
      </div>
    </div>
  );
}

export const coords = (lat: number, lon: number, d = 4) => `${fmtLat(lat, d)}  ${fmtLon(lon, d)}`;

/* ---------- compact live bar (Explore) ---------- */
export function LiveBar({ s, setTime, setPlaying, setSpeed, children }: { s: Shared; children?: ReactNode } & Ctl) {
  const d = new Date(s.timeMs);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).toUpperCase();
  const time = d.toISOString().slice(11, 19);
  const idx = SPEEDS.indexOf(s.speed);
  return (
    <section aria-label="Time" className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/70 to-transparent px-4 pt-10 pb-4">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
        <span className="flex items-center gap-2 font-display text-lg font-bold tracking-[0.1em] text-mint"><i className="size-2.5 rounded-full bg-mint" />SIM</span>
        <span className="font-display text-base font-semibold tracking-[0.08em] tabular">{date}</span>
        <button type="button" aria-pressed={s.playing} aria-label={s.playing ? 'Pause' : 'Play'}
          onClick={() => { if (!s.playing && s.timeMs >= s.endMs) setTime(s.startMs); setPlaying(!s.playing); }}
          className="flex size-11 items-center justify-center rounded-full border-2 border-mint text-mint hover:bg-mint/15"><PlayIcon playing={s.playing} /></button>
        <button type="button" onClick={() => setSpeed(SPEEDS[(idx + 1) % SPEEDS.length])} aria-label="Change speed" className="font-display text-base font-semibold tracking-[0.08em] text-mint">
          {s.speed >= 24 ? `${s.speed / 24} DAY/S` : `${s.speed} H/S`}
        </button>
        <span className="font-display text-base font-semibold tracking-[0.08em] tabular">{time}</span>
      </div>
      <label className="sr-only" htmlFor="live-scrub">Time within the selected range</label>
      <input id="live-scrub" type="range" min={s.startMs} max={s.endMs} step={STEP} value={s.timeMs} onChange={(e) => setTime(Number(e.target.value))} className="mx-auto mt-3 block w-full max-w-3xl" />
      {children && <div className="mx-auto mt-4 max-w-3xl border-t border-white/15 pt-3">{children}</div>}
    </section>
  );
}
