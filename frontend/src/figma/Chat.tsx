import { useTranslation } from "../i18n/language";
import { useEffect, useRef, useState } from "react";
import { useAssistant } from "../mvp/useAssistant";
import { DecisionBadge } from "../mvp/DecisionBadge";
import { assistantErrorMessage } from "../mvp/assistantErrors";
export { useAssistant };
export type Assistant = ReturnType<typeof useAssistant>;
const SUGGEST = [
  "Compare Haworth and Nobile Rim 1.",
  "Only select Haworth, keeping the schedule and hardware.",
  "Set minimum sunlight to 90%, keep the site and arrival.",
];
const GENERAL_SUGGEST = [
  "If my lunar south-pole mission schedule changes, what can HOSA help me decide?",
  "How does INDETERMINATE differ from FAIL?",
  "Which data sources does HOSA use to evaluate sunlight and Earth visibility?",
];
const REQUEST_LABELS: Record<string, string> = {
  illumination_model: "Illumination model", scenario_id: "Scenario", arrival_utc: "Arrival · UTC",
  duration_hours: "Mission hours", hardware: "Hardware", sun_panel: "Panel height · m",
  earth_antenna: "Antenna height · m", constraints: "Secondary preferences",
  max_darkness_hours: "Longest darkness preference · h",
  max_earth_blackout_hours: "Longest Earth blackout preference · h",
  min_sunlit_fraction: "Minimum sunlight fraction", min_earth_los_fraction: "Minimum Earth visibility fraction",
  current_site_id: "Current site", data_source: "Data source", site_ids: "Selected sites",
  rank_by: "Rank by", search_from_utc: "Search from · UTC", search_until_utc: "Search until · UTC",
};

export function RequestDetails({ value }: { value: Record<string, unknown> }) {
  const { t: tr } = useTranslation();
  return <dl className="space-y-2 text-xs">
    {Object.entries(value).map(([key, item]) => <div key={key} className="border-l border-line pl-3">
      <dt className="text-mute">{tr(REQUEST_LABELS[key] ?? key)}</dt>
      <dd className="mt-1 break-words text-soft">
        {item && typeof item === "object" && !Array.isArray(item)
          ? <RequestDetails value={item as Record<string, unknown>} />
          : Array.isArray(item) ? item.join(", ")
          : item == null ? tr("Not specified")
          : typeof item === "boolean" ? tr(item ? "Yes" : "No")
          : key === "data_source" || key === "illumination_model" || key === "rank_by"
            ? tr(String(item)) : String(item)}
      </dd>
    </div>)}
  </dl>;
}

export function ChatThread({
  a,
  page = false,
}: {
  a: Assistant;
  page?: boolean;
}) {
  const { t: tr } = useTranslation();
  const { messages, busy, review, outcome, baseline, caps, error, mode, run } = a;
  const general = mode === "general";
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages, busy, review]);
  const pad = page ? "px-5 sm:px-8" : "px-5";
  return (
    <>
      <div className={`flex shrink-0 gap-1 border-b border-line py-2 ${pad}`} role="group" aria-label={tr("Assistant mode")}>
        {([["general", "General chat"], ["planning", "Mission planning"]] as const).map(([id, label]) => (
          <button key={id} type="button" aria-pressed={mode === id} onClick={() => a.setMode(id)}
            className={`border px-3 py-1.5 text-xs font-semibold ${mode === id ? "border-white bg-white text-ink" : "border-line text-soft hover:border-white"}`}>
            {tr(label)}
          </button>
        ))}
      </div>
      <div
        className={`min-h-0 flex-1 space-y-5 overflow-y-auto py-5 ${pad}`}
        aria-label={tr("Conversation")}
        aria-live="polite"
      >
        <p className="text-xs leading-relaxed text-mute">
          {tr(general
            ? "Ask what HOSA can do, how to interpret results, or where its data comes from."
            : "Choose any site from Compare, up to two per request. The default mission is 72 hours with a 1 m panel and 2 m antenna. Longer missions or an explicit UTC end date are supported without a duration cap. Review before evaluation.")}
        </p>
        {!general && baseline && (
          <p className="break-words font-mono text-[10px] text-mute">
            {tr("Conversation context: ")}{baseline.current_site_id} ·{" "}
            {baseline.arrival_utc}
          </p>
        )}
        {!caps && !error && (
          <p role="status" className="text-xs text-mute">
            {tr("Loading assistant capabilities…")}
          </p>
        )}
        {caps && !caps.assistant_enabled && (
          <p role="status" className="border border-line p-3 text-sm text-mute">
            {tr("The LLM assistant is disabled on this backend. Configure ASSISTANT_ENABLED and the selected provider’s model and API key on the server. Other views work without an LLM.")}
          </p>
        )}
        {!general && <label className="flex items-start gap-2 text-xs text-mute">
          <input
            type="checkbox"
            checked={a.resolveIndeterminate}
            disabled={busy || !!review || a.hasPending}
            onChange={(e) => a.setResolveIndeterminate(e.target.checked)}
          />
          {tr("Complete inconclusive validation automatically (can take several minutes).")}
          </label>}
        {!messages.length && (
          <div>
            <p
              className={`${page ? "text-lg" : "text-[15px]"} leading-relaxed text-soft`}
            >
              {tr(general
                ? "Ask about lunar mission planning or the evidence behind HOSA’s results."
                : "Describe a change to the mission. You’ll review the request before it is evaluated.")}
            </p>
            <div className={`mt-5 grid gap-2 ${page ? "sm:grid-cols-2" : ""}`}>
              {(general ? GENERAL_SUGGEST : SUGGEST).map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={busy || !caps?.assistant_enabled || !!review}
                  onClick={() => a.setText(tr(q))}
                  className="border border-line px-3 py-3 text-left text-sm text-soft transition hover:border-white hover:text-white disabled:opacity-40"
                >
                  {tr(q)}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.who === "user" ? (
            <div key={m.id ?? i} className="flex justify-end">
              <p
                className={`max-w-[85%] whitespace-pre-wrap break-words bg-white px-3 py-2 text-ink ${page ? "text-[15px]" : "text-sm"}`}
              >
                {m.text}
              </p>
            </div>
          ) : (
            <div key={m.id ?? i} className="border-l-2 border-white pl-3">
              <p
                className={`whitespace-pre-wrap break-words leading-relaxed text-white ${page ? "text-[15px]" : "text-sm"}`}
              >
                {m.text}
              </p>
              {!!m.citations?.length && (
                <details className="mt-2 text-xs text-soft">
                  <summary className="cursor-pointer text-mute">{tr("Sources (")}{tr(m.citations.length)})</summary>
                  <ul className="mt-2 space-y-2">
                    {m.citations.map((source) => (
                      <li key={source.source_id} className="break-words border-l border-line pl-2">
                        <p>{source.path}</p>
                        <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-mute">{source.excerpt}</p>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ),
        )}
        {review && (
          <div className="space-y-3 border border-white/40 p-4">
            <h3 className="font-display text-sm font-semibold tracking-widest">
              {tr("Review interpreted request")}
            </h3>
            <p className="break-words text-sm text-soft">
              {tr(review.draft.spec.site_ids.join(", "))} ·{" "}
              {review.draft.spec.arrival_utc}
              {" → "}{review.draft.spec.end_utc}
              {" · "}{review.draft.spec.duration_hours} {tr("h")}
            </p>
            <p className="text-xs text-mute">
              {tr("Minimum mean visible Sun disc ")}{tr(review.draft.spec.min_sunlit_fraction * 100)}{tr("% · minimum Earth LOS ")}{tr(review.draft.spec.min_earth_los_fraction * 100)}
              %
            </p>
            <details>
              <summary className="cursor-pointer text-xs text-mute">
                {tr("Full request")}
              </summary>
              <div className="mt-2 max-h-64 overflow-auto">
                <RequestDetails value={review.draft.spec} />
              </div>
            </details>
            <div className="flex flex-wrap gap-3">
              <button
                disabled={busy}
                onClick={() => void a.evaluate()}
                className="border border-white bg-white px-3 py-2 font-display text-xs font-semibold text-ink disabled:opacity-40"
              >
                {tr("Confirm evaluation")}
              </button>
              <button
                disabled={busy}
                onClick={a.cancel}
                className="border border-line px-3 py-2 text-xs text-soft disabled:opacity-40"
              >
                {tr("Cancel")}
              </button>
            </div>
          </div>
        )}
        {busy && (
          <div
            role="status"
            className="flex items-center gap-3 border-l-2 border-white/40 pl-3 text-xs text-mute"
          >
            <span className="size-1.5 animate-pulse bg-soft" />
            {tr(run?.stage === "retrieving" || run?.stage === "indexing"
              ? "Finding project sources…" : "Waiting for the backend…")}
            {general && run && (run.status === "queued" || run.status === "running") && (
              <button type="button" onClick={() => void a.stop()} className="underline hover:text-white">{tr("Stop")}</button>
            )}
          </div>
        )}
        {outcome && (
          <div className="space-y-2 border border-line p-3 text-xs text-mute">
            <strong className="text-white">
              {tr(outcome.evidence.status.replaceAll("_", " "))}
            </strong>
            {outcome.evidence.candidates.map((c) => (
              <p key={c.site_id}>
                {c.site_id} <DecisionBadge value={c.decision} />
              </p>
            ))}
            <p>
              {tr(outcome.evidence.apply_allowed
                ? "A feasible candidate is available."
                : "No candidate can be applied from this evaluation.")}
            </p>
          </div>
        )}
        {error && (
          <div role="alert" className="break-words text-sm text-rose">
            <p>{tr(assistantErrorMessage(error))}</p>
            {assistantErrorMessage(error) !== error && <details className="mt-2 text-xs text-mute">
              <summary className="cursor-pointer">{tr("Technical details")}</summary>
              <code>{error}</code>
            </details>}
          </div>
        )}
        <div ref={end} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void a.send();
        }}
        className="flex border-t border-line"
      >
        <label
          className="sr-only"
          htmlFor={page ? "chat-input-page" : "chat-input"}
        >
          {tr("Assistant request")}
        </label>
        <textarea
          id={page ? "chat-input-page" : "chat-input"}
          aria-label={tr("Assistant request")}
          value={a.text}
          maxLength={4000}
          rows={2}
          onChange={(e) => a.setText(e.target.value)}
          disabled={!caps?.assistant_enabled || busy || !!review}
          placeholder={tr("Ask about a site or date")}
          className={`min-w-0 flex-1 resize-none bg-transparent py-4 text-sm text-white placeholder:text-mute focus:outline-none ${pad}`}
        />
        <button
          type="submit"
          disabled={
            !a.text.trim() || !caps?.assistant_enabled || busy || !!review
          }
          aria-label={tr("Send request")}
          className="px-5 font-display text-[13px] font-bold tracking-[0.14em] text-white uppercase disabled:text-mute"
        >
          {tr("Send")}
        </button>
      </form>
    </>
  );
}
export function ChatPage({ a }: { a: Assistant }) {
  const { t: tr } = useTranslation();
  const topics = [
    ["Ask", "Name a site from Compare or describe a change to your mission."],
    ["Review", "Confirm the interpreted requirements before computation."],
    ["Evidence", "Read backend decisions and unknown evidence."],
    ["Continue", "Follow-up turns retain the evaluated site and date."],
  ];
  return (
    <div className="mx-auto flex h-[calc(100svh-3.5rem)] max-w-6xl flex-col lg:flex-row">
      <aside className="shrink-0 border-b border-line p-5 lg:w-[300px] lg:border-r lg:border-b-0 lg:p-8">
        <h2 className="font-display text-3xl font-bold">{tr("Assistant")}</h2>
        <p className="mt-2 text-sm text-mute">
          {tr("Plain questions. Real backend evidence. Review before evaluating.")}
        </p>
        <ul className="mt-6 hidden lg:block">
          {topics.map(([t, d]) => (
            <li key={t} className="border-t border-line py-3">
              <p className="font-display text-sm font-semibold tracking-[0.1em] uppercase">
                {tr(t)}
              </p>
              <p className="mt-1 text-xs text-mute">{tr(d)}</p>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={a.reset}
          className="mt-4 text-xs text-mute underline underline-offset-2 hover:text-white"
        >
          {tr("New conversation")}
        </button>
      </aside>
      <section
        className="flex min-h-0 flex-1 flex-col"
        aria-label={tr("Assistant chat")}
      >
        <ChatThread a={a} page />
      </section>
    </div>
  );
}
export default function ChatDock({
  a,
  hidden,
}: {
  a: Assistant;
  hidden?: boolean;
}) {
  const { t: tr } = useTranslation();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  if (hidden) return null;
  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-label={tr(open ? "Close assistant" : "Open assistant")}
          className="fixed right-4 bottom-4 z-50 flex h-12 items-center gap-2 bg-white px-4 font-display text-[13px] font-bold tracking-[0.14em] text-ink uppercase hover:bg-soft max-sm:right-3 max-sm:bottom-3"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            aria-hidden="true"
          >
            {open ? (
              <path d="M3 3l10 10M13 3L3 13" />
            ) : (
              <path d="M2 3h12v8H7l-3 3v-3H2z" strokeLinejoin="round" />
            )}
          </svg>
          {tr(open ? "Close" : "Ask")}
        </button>
      )}
      {open && (
        <section
          role="dialog"
          aria-label={tr("Assistant")}
          className="fixed top-14 right-0 bottom-0 z-40 flex w-full flex-col border-l border-line bg-panel sm:w-[380px]"
        >
          <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <div>
              <h2 className="font-display text-[15px] font-bold tracking-[0.12em]">
                {tr("Assistant")}
              </h2>
              <p className="mt-0.5 text-[11px] text-mute">
                {tr("Project questions and mission planning")}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <button
                type="button"
                onClick={a.reset}
                className="text-xs text-mute underline underline-offset-2 hover:text-white"
              >
                {tr("New conversation")}
              </button>
              <button
                type="button"
                aria-label={tr("Close assistant")}
                onClick={() => setOpen(false)}
                className="p-1 text-soft hover:text-white"
              >
                {tr("×")}
              </button>
            </div>
          </header>
          <ChatThread a={a} />
        </section>
      )}
    </>
  );
}
