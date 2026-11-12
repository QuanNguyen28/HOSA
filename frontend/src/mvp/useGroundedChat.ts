import { useEffect, useRef, useState } from "react";
import { api, wait } from "./api";

const SESSION_KEY = "lunarsight.knowledge-session";

export type Citation = {
  source_id: string;
  path: string;
  excerpt: string;
  source_status?: string;
};
export type ChatMessage = {
  id?: string;
  who: "user" | "assistant";
  text: string;
  citations?: Citation[];
};
type Run = {
  id: string;
  status: "queued" | "running" | "completed" | "needs_input" | "partial" |
    "failed" | "interrupted" | "cancelled";
  stage: string;
  error_code?: string | null;
  result?: { citations?: Citation[]; next_action?: "prepare_mission" } | null;
};
type Session = {
  id: string;
  runs: Run[];
  messages: { id: string; role: string; content: string; run_id?: string }[];
};

const pending = (run: Run) => run.status === "queued" || run.status === "running";
const sessionPath = (id: string) => `/assistant/sessions/${encodeURIComponent(id)}`;
const runPath = (id: string) => `/assistant/runs/${encodeURIComponent(id)}`;

function remember(id: string | null) {
  try {
    if (id) localStorage.setItem(SESSION_KEY, id);
    else localStorage.removeItem(SESSION_KEY);
  } catch { /* Chat still works when browser storage is unavailable. */ }
}

export function useGroundedChat(enabled: boolean) {
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const sessionId = useRef<string | null>(null);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);

  const readSession = async (id: string, signal: AbortSignal) => {
    const session = await api<Session>(sessionPath(id), signal);
    if (signal.aborted) return session;
    const runs = new Map(session.runs.map((item) => [item.id, item]));
    setMessages(session.messages.flatMap((m): ChatMessage[] =>
      m.role === "user" || m.role === "assistant" ? [{
        id: m.id, who: m.role, text: m.content,
        citations: m.role === "assistant" ? runs.get(m.run_id ?? "")?.result?.citations : undefined,
      }] : []));
    return session;
  };

  const follow = async (id: string, current: Run, signal: AbortSignal) => {
    for (;;) {
      if (signal.aborted) return;
      setRun(current);
      if (!pending(current)) break;
      await wait(700, signal);
      current = await api<Run>(runPath(current.id), signal);
    }
    await readSession(id, signal);
    if (!signal.aborted && (current.status === "failed" || current.status === "interrupted"))
      setError(current.error_code ?? "Assistant could not complete this turn.");
    if (!signal.aborted) return current;
  };

  useEffect(() => {
    if (!enabled) return;
    let stored: string | null = null;
    try { stored = localStorage.getItem(SESSION_KEY); } catch { /* optional storage */ }
    if (!stored) return;
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    const id = stored;
    void (async () => {
      try {
        const session = await readSession(id, controller.signal);
        if (controller.signal.aborted) return;
        sessionId.current = id;
        const latest = session.runs.at(-1);
        if (latest) await follow(id, latest, controller.signal);
      } catch (e) {
        if (controller.signal.aborted) return;
        if (e instanceof Error && e.message === "SESSION_NOT_FOUND") remember(null);
        else setError(e instanceof Error ? e.message : "Could not restore conversation.");
      } finally {
        if (!controller.signal.aborted) {
          active.current = null;
          setBusy(false);
        }
      }
    })();
    return () => {
      active.current?.abort();
      active.current = null;
    };
  }, [enabled]);

  const send = async () => {
    const prompt = text.trim();
    if (!enabled || active.current || !prompt) return;
    const controller = new AbortController();
    const { signal } = controller;
    active.current = controller;
    setBusy(true);
    setError("");
    setRun(null);
    try {
      let id = sessionId.current;
      if (!id) {
        const created = await api<Session>("/assistant/sessions", signal, {});
        if (signal.aborted) return;
        sessionId.current = id = created.id;
        remember(id);
      }
      const accepted = await api<Run>(`${sessionPath(id)}/messages`, signal,
        { text: prompt, knowledge_only: true }, { "Idempotency-Key": crypto.randomUUID() });
      if (signal.aborted) return;
      setText("");
      setMessages((old) => [...old, { who: "user", text: prompt }]);
      return await follow(id, accepted, signal);
    } catch (e) {
      if (!signal.aborted) setError(e instanceof Error ? e.message : "Could not send message.");
    } finally {
      if (!signal.aborted) {
        active.current = null;
        setBusy(false);
      }
    }
  };

  const stop = async () => {
    if (!run || !pending(run)) return;
    try { await api(`${runPath(run.id)}/cancel`, active.current?.signal, {}); }
    catch (e) {
      if (active.current && !active.current.signal.aborted)
        setError(e instanceof Error ? e.message : "Could not stop this turn.");
    }
  };

  const reset = () => {
    if (run && pending(run)) void api(`${runPath(run.id)}/cancel`, undefined, {}).catch(() => {});
    active.current?.abort();
    active.current = null;
    sessionId.current = null;
    remember(null);
    setBusy(false);
    setRun(null);
    setError("");
    setText("");
    setMessages([]);
  };
  return { text, setText, messages, busy, run, error, send, stop, reset };
}
