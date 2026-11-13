import { useTranslation } from "../i18n/LanguageProvider";
import { type ReactNode } from "react";
import { SPEEDS, STEP, fmtLat, fmtLon } from "./model";

export const clamp = (v: number, a: number, b: number) =>
  Math.min(b, Math.max(a, v));

export type Shared = {
  startMs: number;
  endMs: number;
  timeMs: number;
  playing: boolean;
  speed: number;
  dark: number;
  margin: number;
  hIdx: number;
};
export type Ctl = {
  setRange: (a: number, b: number) => void;
  setTime: (f: number | ((t: number) => number)) => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (n: number) => void;
};

/* ---------- icons ---------- */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle
        cx="16"
        cy="16"
        r="15"
        fill="none"
        stroke="#fff"
        strokeWidth="1.2"
      />
      <path
        d="M20.5 9.2a7.8 7.8 0 1 0 2.3 11.4A6.3 6.3 0 0 1 20.5 9.2Z"
        fill="none"
        stroke="#fff"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="22.5" cy="9.5" r="1.6" fill="#ffc53d" />
    </svg>
  );
}
export function SunIcon({
  className = "",
  size = 16,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden="true"
      className={className}
    >
      <circle cx="8" cy="8" r="3.2" fill="currentColor" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
        <line
          key={a}
          x1="8"
          y1="1.2"
          x2="8"
          y2="3"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          transform={`rotate(${a} 8 8)`}
        />
      ))}
    </svg>
  );
}
export function EarthIcon({
  className = "",
  size = 16,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden="true"
      className={className}
    >
      <circle
        cx="8"
        cy="8"
        r="6.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <ellipse
        cx="8"
        cy="8"
        rx="2.6"
        ry="6.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.1"
      />
      <line
        x1="1.8"
        y1="8"
        x2="14.2"
        y2="8"
        stroke="currentColor"
        strokeWidth="1.1"
      />
    </svg>
  );
}
export const PlayIcon = ({ playing }: { playing: boolean }) =>
  playing ? (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <rect x="2" y="1.5" width="3.4" height="11" rx="1" fill="currentColor" />
      <rect
        x="8.6"
        y="1.5"
        width="3.4"
        height="11"
        rx="1"
        fill="currentColor"
      />
    </svg>
  ) : (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M3 1.8v10.4a.6.6 0 0 0 .9.5l8.3-5.2a.6.6 0 0 0 0-1L3.9 1.3a.6.6 0 0 0-.9.5Z"
        fill="currentColor"
      />
    </svg>
  );

/* ---------- ring gauge ---------- */
export function Ring({
  value,
  label,
  color,
  icon,
  size = 112,
  best,
  suffix = "%",
}: {
  value: number;
  label: string;
  color: string;
  icon?: ReactNode;
  size?: number;
  best?: boolean;
  suffix?: string;
}) {
  const { t: tr } = useTranslation();
  const r = size / 2 - 8,
    c = 2 * Math.PI * r,
    v = clamp(value, 0, 100);
  return (
    <div
      className="flex flex-col items-center gap-2"
      role="img"
      aria-label={tr("{0}: {1}{2}", [label, value.toFixed(0), suffix])}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="#14232a"
            strokeWidth="4"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="4"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - v / 100)}
            style={{
              transition: "stroke-dashoffset .6s cubic-bezier(.2,.8,.2,1)",
              filter: "none",
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-2xl font-semibold tabular">
            {value.toFixed(0)}
            <span className="text-sm text-mute">{tr(suffix)}</span>
          </span>
        </div>
        {best && (
          <span className="absolute -top-2 left-1/2 -translate-x-1/2 bg-white px-1.5 font-display text-[10px] font-bold tracking-widest text-ink">
            {tr("TOP")}
          </span>
        )}
      </div>
      <span className="flex items-center gap-1.5 text-xs text-soft">
        {icon}
        {tr(label)}
      </span>
    </div>
  );
}

export function Seg<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { v: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
}) {
  const { t: tr } = useTranslation();
  return (
    <div
      role="radiogroup"
      aria-label={tr(label)}
      className="inline-flex border border-line bg-ink/85"
    >
      {options.map((o) => (
        <button
          key={String(o.v)}
          type="button"
          role="radio"
          aria-checked={o.v === value}
          onClick={() => onChange(o.v)}
          className={`px-4 py-2 font-display text-[12px] font-semibold tracking-[0.14em] whitespace-nowrap uppercase transition ${o.v === value ? "bg-white text-ink" : "text-soft hover:text-white"}`}
        >
          {tr(o.label)}
        </button>
      ))}
    </div>
  );
}

export const coords = (lat: number, lon: number, d = 4) =>
  `${fmtLat(lat, d)}  ${fmtLon(lon, d)}`;

/* ---------- compact live bar (Explore) ---------- */
export function LiveBar({
  s,
  setTime,
  setPlaying,
  setSpeed,
  children,
}: { s: Shared; children?: ReactNode } & Ctl) {
  const { t: tr, locale } = useTranslation();
  const d = new Date(s.timeMs);
  const date = d
    .toLocaleDateString(locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    })
    .toUpperCase();
  const time = d.toISOString().slice(11, 19);
  const idx = SPEEDS.indexOf(s.speed);
  const ended = s.timeMs >= s.endMs-STEP;
  const pausedMidway = !s.playing && !ended && s.timeMs > s.startMs;
  const primaryLabel = s.playing ? "Pause" : ended ? "Replay" : pausedMidway ? "Continue" : "Play";
  const replay = () => { setTime(s.startMs); setPlaying(true); };
  return (
    <section
      aria-label={tr("Time")}
      className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/70 to-transparent px-4 pt-10 pb-4"
    >
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
        <span className="flex items-center gap-2 font-display text-lg font-bold tracking-[0.1em] text-mint">
          <i className="size-2.5 rounded-full bg-mint" />
          {tr("SIM")}
        </span>
        <span className="font-display text-base font-semibold tracking-[0.08em] tabular">
          {date}
        </span>
        <div className="flex items-start gap-3">
          <div className="flex flex-col items-center gap-1">
            <button
              type="button"
              aria-pressed={ended ? undefined : s.playing}
              aria-label={tr(primaryLabel)}
              onClick={() => ended && !s.playing ? replay() : setPlaying(!s.playing)}
              className="flex size-11 items-center justify-center rounded-full border-2 border-mint text-mint hover:bg-mint/15"
            >
              {ended && !s.playing ? <ReplayIcon /> : <PlayIcon playing={s.playing} />}
            </button>
            <span className="font-mono text-[9px] text-mint">{tr(primaryLabel)}</span>
          </div>
          {pausedMidway && <div className="flex flex-col items-center gap-1">
            <button type="button" aria-label={tr("Replay")} onClick={replay}
              className="flex size-11 items-center justify-center rounded-full border border-white/40 text-soft hover:bg-white/10">
              <ReplayIcon />
            </button>
            <span className="font-mono text-[9px] text-soft">{tr("Replay")}</span>
          </div>}
        </div>
        <button
          type="button"
          onClick={() => setSpeed(SPEEDS[(idx + 1) % SPEEDS.length])}
          aria-label={tr("Change speed")}
          className="font-display text-base font-semibold tracking-[0.08em] text-mint"
        >
          {tr(s.speed >= 24 ? tr("{0} DAY/S", [s.speed / 24]) : tr("{0} H/S", [s.speed]))}
        </button>
        <span className="font-display text-base font-semibold tracking-[0.08em] tabular">
          {time}
        </span>
      </div>
      <label className="sr-only" htmlFor="live-scrub">
        {tr("Time within the selected range")}
      </label>
      <input
        id="live-scrub"
        type="range"
        min={0}
        max={Math.max(0, Math.round((s.endMs - s.startMs) / STEP) - 1)}
        step={1}
        value={Math.round((s.timeMs - s.startMs) / STEP)}
        onChange={(e) => setTime(s.startMs + Number(e.target.value) * STEP)}
        className="mx-auto mt-3 block w-full max-w-3xl"
      />
      {children && (
        <div className="mx-auto mt-4 max-w-3xl border-t border-white/15 pt-3">
          {children}
        </div>
      )}
    </section>
  );
}

function ReplayIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
    <path d="M4 10a8 8 0 1 1 .5 6M4 4v6h6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}
