import { useEffect, useRef, useState } from 'react';
import { SITES, HEIGHTS, DAY, STEP, buildSeries, metrics, fmtDate, fmtDur, type Site } from './model';
import type { Shared } from './ui';

type Msg = { id: number; role: 'user' | 'bot'; text: string; actions?: { label: string; run: () => void }[] };
type Props = {
  s: Shared; siteId: string;
  onSite: (id: string) => void; onCompare: (ids: string[]) => void; onRange: (from: number, days: number) => void;
};

const norm = (x: string) => x.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
const isVi = (q: string) => /[àáảãạăâđêôơưèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ]/i.test(q) || /\b(toi|ban|nao|nhat|khi nao|ngay|so sanh|mat troi|trai dat)\b/.test(norm(q));

const SUGGEST = ['Best site for these dates', 'How long is the dark here?', 'When is the best time to land?', 'Compare the top 3 sites'];

function findSite(q: string): Site | undefined {
  const n = norm(q);
  return SITES.find((x) => n.includes(norm(x.name))) ?? SITES.find((x) => norm(x.name).split(' ').filter((w) => w.length > 4).some((w) => n.includes(w)));
}

export function useAssistant({ s, siteId, onSite, onCompare, onRange }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const idc = useRef(1);
  const h = HEIGHTS[s.hIdx];
  const rangeText = `${fmtDate(s.startMs)} → ${fmtDate(s.endMs - DAY)}`;

  function answer(q: string): Omit<Msg, 'id' | 'role'> {
    const vi = isVi(q), t = (a: string, b: string) => (vi ? a : b), n = norm(q);
    const named = findSite(q);
    const site = named ?? SITES.find((x) => x.id === siteId)!;
    const sm = () => metrics(buildSeries(site, h, s.startMs, s.endMs), s.dark, s.margin);

    if (/(so sanh|compare|top 3)/.test(n)) {
      const rank = SITES.map((x) => ({ x, m: metrics(buildSeries(x, h, s.startMs, s.endMs), s.dark, s.margin) })).sort((a, b) => b.m.bothPct - a.m.bothPct).slice(0, 3);
      return { text: t(`Đã chọn 3 site có thời gian vừa có nắng vừa liên lạc được với Trái Đất nhiều nhất: ${rank.map((r) => `${r.x.name} (${r.m.bothPct.toFixed(0)}%)`).join(', ')}.`, `The 3 sites with the most time of sunlight and an Earth link together: ${rank.map((r) => `${r.x.name} (${r.m.bothPct.toFixed(0)}%)`).join(', ')}.`),
        actions: [{ label: t('Xem so sánh', 'Open comparison'), run: () => onCompare(rank.map((r) => r.x.id)) }] };
    }
    if (/(tot nhat|nen chon|best site|best place|recommend|which site|site nao)/.test(n) && !/(ngay|date|when|khi nao)/.test(n)) {
      const rank = SITES.map((x) => ({ x, m: metrics(buildSeries(x, h, s.startMs, s.endMs), s.dark, s.margin) })).sort((a, b) => b.m.bothPct - a.m.bothPct);
      const b = rank[0];
      return { text: t(`Với ${rangeText}, ${b.x.name} tốt nhất: ${b.m.bothPct.toFixed(0)}% thời gian có cả nắng và liên lạc Trái Đất. Đứng sau là ${rank[1].x.name} (${rank[1].m.bothPct.toFixed(0)}%) và ${rank[2].x.name} (${rank[2].m.bothPct.toFixed(0)}%).`,
        `For ${rangeText}, ${b.x.name} is best: ${b.m.bothPct.toFixed(0)}% of the time has both sunlight and an Earth link. Next are ${rank[1].x.name} (${rank[1].m.bothPct.toFixed(0)}%) and ${rank[2].x.name} (${rank[2].m.bothPct.toFixed(0)}%).`),
        actions: [{ label: t(`Xem ${b.x.name}`, `Show ${b.x.name}`), run: () => onSite(b.x.id) }] };
    }
    if (/(ngay|date|when|khi nao|window|thoi diem)/.test(n)) {
      const y = new Date(s.startMs).getUTCFullYear(), a = Date.UTC(y, 0, 1), len = 14;
      const se = buildSeries(site, h, a, Date.UTC(y + 1, 0, 1) + len * DAY);
      const per = DAY / STEP, pre = new Float64Array(se.n + 1);
      for (let i = 0; i < se.n; i++) pre[i + 1] = pre[i] + (se.fSun[i] > s.dark && se.earthClear[i] > s.margin ? 1 : 0);
      let best = 0, bi = 0;
      for (let d = 0; d < 365; d += 7) { const i0 = d * per, i1 = Math.min(se.n, i0 + len * per), v = (pre[i1] - pre[i0]) / (i1 - i0); if (v > best) { best = v; bi = d; } }
      const start = a + bi * DAY;
      return { text: t(`Với ${site.name} trong năm ${y}, 14 ngày tốt nhất bắt đầu từ ${fmtDate(start)}: ${(best * 100).toFixed(0)}% thời gian có cả nắng và liên lạc Trái Đất.`, `For ${site.name} in ${y}, the best 14 days start on ${fmtDate(start)}: ${(best * 100).toFixed(0)}% of the time has both sunlight and an Earth link.`),
        actions: [{ label: t('Xem ngày này', 'Go to these dates'), run: () => { onSite(site.id); onRange(start, len); } }] };
    }
    if (/(toi|dark|dem|night|dark)/.test(n)) {
      const m = sm();
      return { text: t(`${site.name}: đêm dài nhất ${fmtDur(m.longestDark)} trong ${rangeText}. Pin phải chịu được chừng đó thời gian.`, `${site.name}: the longest dark is ${fmtDur(m.longestDark)} during ${rangeText}. A battery has to last that long.`) };
    }
    if (/(trai dat|earth|lien lac|link|signal|blackout)/.test(n)) {
      const m = sm();
      return { text: t(`${site.name}: nhìn thấy Trái Đất ${m.earthPct.toFixed(0)}% thời gian. Mất liên lạc dài nhất ${fmtDur(m.longestBlackout)}.`, `${site.name}: Earth is in view ${m.earthPct.toFixed(0)}% of the time. The longest blackout is ${fmtDur(m.longestBlackout)}.`) };
    }
    if (/(nang|anh sang|mat troi|sun|light|solar)/.test(n)) {
      const m = sm();
      return { text: t(`${site.name}: có nắng trung bình ${m.sunMeanPct.toFixed(0)}% thời gian trong ${rangeText} (độ cao ${h} m).`, `${site.name}: sunlight averages ${m.sunMeanPct.toFixed(0)}% over ${rangeText} (${h} m height).`) };
    }
    if (named) {
      const m = sm();
      return { text: t(`${site.name}: nắng ${m.sunMeanPct.toFixed(0)}%, thấy Trái Đất ${m.earthPct.toFixed(0)}%, cả hai ${m.bothPct.toFixed(0)}%.`, `${site.name}: sunlight ${m.sunMeanPct.toFixed(0)}%, Earth ${m.earthPct.toFixed(0)}%, both ${m.bothPct.toFixed(0)}%.`),
        actions: [{ label: t('Xem trên Mặt Trăng', 'Show on the Moon'), run: () => onSite(site.id) }] };
    }
    return { text: t('Mình chưa hiểu câu này. Bạn thử hỏi về site nào tốt nhất, ngày hạ cánh tốt nhất, thời gian tối, hoặc tên một site.', "I didn't catch that. Try asking for the best site, the best landing dates, how long the dark lasts, or name a site.") };
  }

  function send(q: string) {
    const v = q.trim(); if (!v || busy) return;
    setBusy(true);
    setMsgs((m) => [...m, { id: idc.current++, role: 'user', text: v }]);
    window.setTimeout(() => {
      let r: Omit<Msg, 'id' | 'role'>;
      try { r = answer(v); } catch { r = { text: 'Something went wrong while computing that. Please try again.' }; }
      setMsgs((m) => [...m, { id: idc.current++, role: 'bot', ...r }]); setBusy(false);
    }, 450);
  }

  return { msgs, busy, send, clear: () => setMsgs([]) };
}
export type Assistant = ReturnType<typeof useAssistant>;

export function ChatThread({ a, page = false, onAction }: { a: Assistant; page?: boolean; onAction?: () => void }) {
  const [text, setText] = useState('');
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const { msgs, busy, send } = a;
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [msgs, busy]);
  useEffect(() => { input.current?.focus(); }, []);
  const submit = (q: string) => { if (!q.trim() || busy) return; setText(''); send(q); };
  const pad = page ? 'px-5 sm:px-8' : 'px-5';
  return (
    <>
      <div className={`min-h-0 flex-1 space-y-5 overflow-y-auto py-5 ${pad}`} aria-live="polite">
        {msgs.length === 0 && (
          <div>
            <p className={`${page ? 'text-lg' : 'text-[15px]'} leading-relaxed text-soft`}>Hi. Ask me about sunlight, Earth visibility and landing dates at the lunar south pole.</p>
            <div className={`mt-5 grid gap-2 ${page ? 'sm:grid-cols-2' : ''}`}>
              {SUGGEST.map((q) => <button key={q} type="button" onClick={() => submit(q)} className="border border-line px-3 py-3 text-left text-sm text-soft transition hover:border-white hover:text-white">{q}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m) => m.role === 'user' ? (
          <div key={m.id} className="flex justify-end"><p className={`max-w-[85%] bg-white px-3 py-2 text-ink ${page ? 'text-[15px]' : 'text-sm'}`}>{m.text}</p></div>
        ) : (
          <div key={m.id} className="border-l-2 border-white pl-3">
            <p className={`leading-relaxed text-white ${page ? 'text-[15px]' : 'text-sm'}`}>{m.text}</p>
            {m.actions && <div className="mt-3 flex flex-wrap gap-2">{m.actions.map((x) => (
              <button key={x.label} type="button" onClick={() => { x.run(); onAction?.(); }} className="border border-white/50 px-3 py-1.5 font-display text-[12px] font-semibold tracking-[0.12em] uppercase hover:bg-white hover:text-ink">{x.label} →</button>
            ))}</div>}
          </div>
        ))}
        {busy && <div className="flex gap-1 border-l-2 border-white/40 pl-3" aria-label="Typing">{[0, 1, 2].map((i) => <i key={i} className="size-1.5 animate-pulse bg-soft" style={{ animationDelay: `${i * 150}ms` }} />)}</div>}
        <div ref={end} />
      </div>
      {msgs.length > 0 && (
        <div className={`flex gap-2 overflow-x-auto border-t border-line py-2.5 ${pad}`}>
          {SUGGEST.map((q) => <button key={q} type="button" onClick={() => submit(q)} className="shrink-0 border border-line px-2.5 py-1 text-xs text-mute hover:border-white hover:text-white">{q}</button>)}
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); submit(text); }} className="flex border-t border-line">
        <label className="sr-only" htmlFor={page ? 'chat-input-page' : 'chat-input'}>Message</label>
        <input id={page ? 'chat-input-page' : 'chat-input'} ref={input} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about a site or date" autoComplete="off"
          className={`min-w-0 flex-1 bg-transparent py-4 text-sm text-white placeholder:text-mute focus:outline-none ${pad}`} />
        <button type="submit" disabled={!text.trim() || busy} aria-label="Send" className="px-5 font-display text-[13px] font-bold tracking-[0.14em] text-white uppercase disabled:text-mute">Send</button>
      </form>
    </>
  );
}

/* Full-page assistant tab */
export function ChatPage({ a }: { a: Assistant }) {
  const topics: [string, string][] = [['Best site', 'Which site has the most sunlight and Earth link for your dates.'], ['Best dates', 'The best two weeks to land at any site.'], ['Dark and blackout', 'How long a site stays dark or out of contact.'], ['Compare', 'Put the top three sites side by side.']];
  return (
    <div className="mx-auto flex h-[calc(100svh-3.5rem)] max-w-6xl flex-col lg:flex-row">
      <aside className="shrink-0 border-b border-line p-5 lg:w-[300px] lg:border-r lg:border-b-0 lg:p-8">
        <h2 className="font-display text-3xl font-bold">Assistant</h2>
        <p className="mt-2 text-sm text-mute">Plain questions, quick answers. It reads your selected dates and height.</p>
        <ul className="mt-6 hidden lg:block">
          {topics.map(([t, d]) => <li key={t} className="border-t border-line py-3"><p className="font-display text-sm font-semibold tracking-[0.1em] uppercase">{t}</p><p className="mt-1 text-xs text-mute">{d}</p></li>)}
        </ul>
        <button type="button" onClick={a.clear} className="mt-6 hidden text-xs text-mute underline underline-offset-2 hover:text-white lg:block">Clear conversation</button>
      </aside>
      <section className="flex min-h-0 flex-1 flex-col" aria-label="Conversation"><ChatThread a={a} page /></section>
    </div>
  );
}

export default function ChatDock({ a, hidden }: { a: Assistant; hidden?: boolean }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k);
  }, []);
  if (hidden) return null;
  return (
    <>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={open ? 'Close assistant' : 'Open assistant'}
        className="fixed right-4 bottom-4 z-50 flex h-12 items-center gap-2 bg-white px-4 font-display text-[13px] font-bold tracking-[0.14em] text-ink uppercase hover:bg-soft max-sm:right-3 max-sm:bottom-3">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">{open ? <path d="M3 3l10 10M13 3L3 13" /> : <path d="M2 3h12v8H7l-3 3v-3H2z" strokeLinejoin="round" />}</svg>
        {open ? 'Close' : 'Ask'}
      </button>
      {open && (
        <section role="dialog" aria-label="Assistant" className="fixed top-14 right-0 bottom-0 z-40 flex w-full flex-col border-l border-line bg-panel sm:w-[380px]">
          <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <div><h2 className="font-display text-[15px] font-bold tracking-[0.12em]">Assistant</h2><p className="mt-0.5 text-[11px] text-mute">Answers from this app's simulated data</p></div>
            <button type="button" onClick={a.clear} className="text-xs text-mute underline underline-offset-2 hover:text-white">Clear</button>
          </header>
          <ChatThread a={a} onAction={() => { if (window.innerWidth < 640) setOpen(false); }} />
        </section>
      )}
    </>
  );
}
