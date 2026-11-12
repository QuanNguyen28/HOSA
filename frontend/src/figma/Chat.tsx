import { useEffect, useRef, useState } from "react";
import { useAssistant } from "../mvp/useAssistant";
import { DecisionBadge } from "../mvp/DecisionBadge";
export { useAssistant };
export type Assistant = ReturnType<typeof useAssistant>;
const SUGGEST = [
  "Compare Site01_P1 and Site04_P1 on 2026-11-17T00:00:00Z, keep the hardware.",
  "Chỉ chọn Site04_P1, giữ nguyên lịch và phần cứng.",
  "Set minimum sunlight to 90%, keep the site and arrival.",
];
export function ChatThread({
  a,
  page = false,
}: {
  a: Assistant;
  page?: boolean;
}) {
  const { messages, busy, review, outcome, baseline, caps, error } = a;
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages, busy, review]);
  const pad = page ? "px-5 sm:px-8" : "px-5";
  return (
    <>
      <div
        className={`min-h-0 flex-1 space-y-5 overflow-y-auto py-5 ${pad}`}
        aria-label="Conversation"
        aria-live="polite"
      >
        <p className="text-xs leading-relaxed text-mute">
          Default mission: Site01/Site04, 72 hours, panel 1 m / antenna 2 m.
          Longer missions use verified terrain and JPL data without a duration
          cap. This conversation keeps its own mission context.
          Coordinate/contact settings are in Explore, Compare and Best dates.
        </p>
        {baseline && (
          <p className="break-words font-mono text-[10px] text-mute">
            Conversation context: {baseline.current_site_id} ·{" "}
            {baseline.arrival_utc}
          </p>
        )}
        {!caps && !error && (
          <p role="status" className="text-xs text-mute">
            Loading assistant capabilities…
          </p>
        )}
        {caps && !caps.assistant_enabled && (
          <p role="status" className="border border-line p-3 text-sm text-mute">
            The LLM assistant is disabled on this backend. Configure
            ASSISTANT_ENABLED, OPENROUTER_MODEL and OPENROUTER_API_KEY on the
            server. Other views work without an LLM.
          </p>
        )}
        <label className="flex items-start gap-2 text-xs text-mute">
          <input
            type="checkbox"
            checked={a.resolveIndeterminate}
            disabled={busy || !!review || a.hasPending}
            onChange={(e) => a.setResolveIndeterminate(e.target.checked)}
          />
          Complete inconclusive validation automatically (can take several
          minutes).
        </label>
        {!messages.length && (
          <div>
            <p
              className={`${page ? "text-lg" : "text-[15px]"} leading-relaxed text-soft`}
            >
              Hi. Ask me about sunlight, Earth visibility and landing dates at
              the lunar south pole. Review the interpreted request before
              evaluation.
            </p>
            <div className={`mt-5 grid gap-2 ${page ? "sm:grid-cols-2" : ""}`}>
              {SUGGEST.map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={busy || !caps?.assistant_enabled || !!review}
                  onClick={() => a.setText(q)}
                  className="border border-line px-3 py-3 text-left text-sm text-soft transition hover:border-white hover:text-white disabled:opacity-40"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.who === "user" ? (
            <div key={i} className="flex justify-end">
              <p
                className={`max-w-[85%] whitespace-pre-wrap break-words bg-white px-3 py-2 text-ink ${page ? "text-[15px]" : "text-sm"}`}
              >
                {m.text}
              </p>
            </div>
          ) : (
            <div key={i} className="border-l-2 border-white pl-3">
              <p
                className={`whitespace-pre-wrap break-words leading-relaxed text-white ${page ? "text-[15px]" : "text-sm"}`}
              >
                {m.text}
              </p>
            </div>
          ),
        )}
        {review && (
          <div className="space-y-3 border border-white/40 p-4">
            <h3 className="font-display text-sm font-semibold tracking-widest">
              Review interpreted request
            </h3>
            <p className="break-words text-sm text-soft">
              {review.draft.spec.site_ids.join(", ")} ·{" "}
              {review.draft.spec.arrival_utc}
            </p>
            <p className="text-xs text-mute">
              Minimum sunlight {review.draft.spec.min_sunlit_fraction * 100}% ·
              minimum Earth LOS {review.draft.spec.min_earth_los_fraction * 100}
              %
            </p>
            <details>
              <summary className="cursor-pointer text-xs text-mute">
                Full request
              </summary>
              <pre className="mt-2 max-h-64 overflow-auto text-[10px]">
                {JSON.stringify(review.draft.spec, null, 2)}
              </pre>
            </details>
            <div className="flex flex-wrap gap-3">
              <button
                disabled={busy}
                onClick={() => void a.evaluate()}
                className="border border-white bg-white px-3 py-2 font-display text-xs font-semibold text-ink disabled:opacity-40"
              >
                Confirm evaluation
              </button>
              <button
                disabled={busy}
                onClick={a.cancel}
                className="border border-line px-3 py-2 text-xs text-soft disabled:opacity-40"
              >
                Cancel
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
            Waiting for the backend…
          </div>
        )}
        {outcome && (
          <div className="space-y-2 border border-line p-3 text-xs text-mute">
            <strong className="text-white">
              {outcome.evidence.status.replaceAll("_", " ")}
            </strong>
            {outcome.evidence.candidates.map((c) => (
              <p key={c.site_id}>
                {c.site_id} <DecisionBadge value={c.decision} />
              </p>
            ))}
            <p>
              {outcome.evidence.apply_allowed
                ? "A feasible candidate is available."
                : "No candidate can be applied from this evaluation."}
            </p>
          </div>
        )}
        {error && (
          <p role="alert" className="break-words text-sm text-rose">
            {error}
          </p>
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
          Assistant request
        </label>
        <textarea
          id={page ? "chat-input-page" : "chat-input"}
          aria-label="Assistant request"
          value={a.text}
          maxLength={4000}
          rows={2}
          onChange={(e) => a.setText(e.target.value)}
          disabled={!caps?.assistant_enabled || busy || !!review}
          placeholder="Ask about a site or date"
          className={`min-w-0 flex-1 resize-none bg-transparent py-4 text-sm text-white placeholder:text-mute focus:outline-none ${pad}`}
        />
        <button
          type="submit"
          disabled={
            !a.text.trim() || !caps?.assistant_enabled || busy || !!review
          }
          aria-label="Send request"
          className="px-5 font-display text-[13px] font-bold tracking-[0.14em] text-white uppercase disabled:text-mute"
        >
          Send
        </button>
      </form>
    </>
  );
}
export function ChatPage({ a }: { a: Assistant }) {
  const topics = [
    ["Ask", "Describe a change to the snapshot mission."],
    ["Review", "Confirm the interpreted requirements before computation."],
    ["Evidence", "Read backend decisions and unknown evidence."],
    ["Continue", "Follow-up turns retain the evaluated site and date."],
  ];
  return (
    <div className="mx-auto flex h-[calc(100svh-3.5rem)] max-w-6xl flex-col lg:flex-row">
      <aside className="shrink-0 border-b border-line p-5 lg:w-[300px] lg:border-r lg:border-b-0 lg:p-8">
        <h2 className="font-display text-3xl font-bold">Assistant</h2>
        <p className="mt-2 text-sm text-mute">
          Plain questions. Real backend evidence. Review before evaluating.
        </p>
        <ul className="mt-6 hidden lg:block">
          {topics.map(([t, d]) => (
            <li key={t} className="border-t border-line py-3">
              <p className="font-display text-sm font-semibold tracking-[0.1em] uppercase">
                {t}
              </p>
              <p className="mt-1 text-xs text-mute">{d}</p>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={a.reset}
          className="mt-4 text-xs text-mute underline underline-offset-2 hover:text-white"
        >
          New conversation
        </button>
      </aside>
      <section
        className="flex min-h-0 flex-1 flex-col"
        aria-label="Assistant chat"
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
          aria-label={open ? "Close assistant" : "Open assistant"}
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
          {open ? "Close" : "Ask"}
        </button>
      )}
      {open && (
        <section
          role="dialog"
          aria-label="Assistant"
          className="fixed top-14 right-0 bottom-0 z-40 flex w-full flex-col border-l border-line bg-panel sm:w-[380px]"
        >
          <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <div>
              <h2 className="font-display text-[15px] font-bold tracking-[0.12em]">
                Assistant
              </h2>
              <p className="mt-0.5 text-[11px] text-mute">
                Answers from the backend snapshot scenario
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <button
                type="button"
                onClick={a.reset}
                className="text-xs text-mute underline underline-offset-2 hover:text-white"
              >
                New conversation
              </button>
              <button
                type="button"
                aria-label="Close assistant"
                onClick={() => setOpen(false)}
                className="p-1 text-soft hover:text-white"
              >
                ×
              </button>
            </div>
          </header>
          <ChatThread a={a} />
        </section>
      )}
    </>
  );
}
