import { useEffect, useRef, useState } from "react";
import { api } from "./api";

type Baseline = {
  scenario_id: string;
  arrival_utc: string;
  duration_hours: number;
  hardware: { sun_panel: number; earth_antenna: number };
  constraints: { max_darkness_hours: number; max_earth_blackout_hours: number };
  min_sunlit_fraction: number;
  min_earth_los_fraction: number;
  current_site_id: string;
};
type Turn = {
  text: string;
  clarifications: { question: string; answer: string }[];
  outcome: "evaluated" | "cancelled";
  summary: string;
};
type Capabilities = {
  assistant_enabled: boolean;
  scenario: {
    scenario_id: string;
    A_utc: string;
    B_utc: string;
    D_hours: number;
    site_ids: string[];
    device_heights_m: Baseline["hardware"];
    example_constraints: Baseline["constraints"];
    example_requirements: {
      min_sunlit_fraction: number;
      min_earth_los_fraction: number;
    };
  };
};
type ParseRequest = {
  resolve_indeterminate: boolean;
  text: string;
  baseline: Baseline;
  selected_site_ids: string[];
  conversation_history: Turn[];
  clarifications: Turn["clarifications"];
  planning_context: {
    rank_by: string;
    search_from_utc: string | null;
    search_until_utc: string | null;
  };
};
type Draft = {
  status: string;
  issues: string[];
  questions: { question: string }[];
  draft_id: string;
  spec_hash: string;
  spec: Baseline & {
    site_ids: string[];
    rank_by: string;
    search_from_utc: string | null;
    search_until_utc: string | null;
  };
};
type Evaluation = {
  explanation: string[];
  explanation_mode: string;
  evidence: {
    status: string;
    apply_allowed: boolean;
    recommended_site_id: string | null;
    candidates: {
      site_id: string;
      decision: string;
      validation?: { passed: boolean; reason_codes?: string[] };
      resolution?: {
        enabled?: boolean;
        status?: string;
        initial_decision?: string;
        refinement_rounds?: number;
        error_code?: string;
      };
    }[];
  };
};
type Message = { who: "user" | "assistant"; text: string };

export function useAssistant() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [error, setError] = useState("");
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<Turn[]>([]);
  const [pending, setPending] = useState<ParseRequest | null>(null);
  const [review, setReview] = useState<{
    draft: Draft;
    request: ParseRequest;
  } | null>(null);
  const [context, setContext] = useState<ParseRequest["planning_context"]>({
    rank_by: "total_earth_los_hours",
    search_from_utc: null,
    search_until_utc: null,
  });
  const [busy, setBusy] = useState(false);
  const [resolveIndeterminate, setResolveIndeterminate] = useState(true);
  const [outcome, setOutcome] = useState<Evaluation | null>(null);
  const active = useRef<AbortController | null>(null);
  const createBaseline = (c: Capabilities): Baseline => ({
    scenario_id: c.scenario.scenario_id,
    arrival_utc: c.scenario.A_utc,
    duration_hours: c.scenario.D_hours,
    hardware: c.scenario.device_heights_m,
    constraints: c.scenario.example_constraints,
    ...c.scenario.example_requirements,
    current_site_id: c.scenario.site_ids[0],
  });
  useEffect(() => {
    const controller = new AbortController();
    api<Capabilities>("/assistant/capabilities", controller.signal)
      .then((c) => {
        setCaps(c);
        setBaseline(createBaseline(c));
        setSelectedSites(c.scenario.site_ids);
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Assistant unavailable.");
      });
    return () => {
      controller.abort();
      active.current?.abort();
    };
  }, []);
  const add = (who: Message["who"], value: string) =>
    setMessages((old) => [...old, { who, text: value }]);
  const send = async () => {
    if (!baseline || !caps?.assistant_enabled || busy || review || !text.trim())
      return;
    const answer = text.trim();
    setText("");
    setError("");
    setOutcome(null);
    add("user", answer);
    setBusy(true);
    const controller = new AbortController();
    active.current = controller;
    const request: ParseRequest = pending
      ? {
          ...pending,
          clarifications: [
            ...pending.clarifications,
            { question: messages.at(-1)?.text ?? "Clarify request", answer },
          ],
        }
      : {
          text: answer,
          resolve_indeterminate: resolveIndeterminate,
          baseline,
          selected_site_ids: selectedSites,
          conversation_history: history.slice(-8),
          clarifications: [],
          planning_context: context,
        };
    try {
      const draft = await api<Draft>(
        "/assistant/parse",
        controller.signal,
        request,
      );
      if (controller.signal.aborted) return;
      if (draft.status === "READY") {
        setReview({ draft, request });
        setPending(null);
      } else {
        const questions = draft.questions.map((q) => q.question).join("\n");
        add("assistant", questions || draft.issues.join(", "));
        setPending(draft.status === "NEEDS_INPUT" ? request : null);
      }
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Unable to parse request.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const evaluate = async () => {
    if (!review || busy) return;
    const { draft, request } = review;
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setError("");
    try {
      const response = await api<Evaluation>(
        "/assistant/evaluate",
        controller.signal,
        {
          draft_id: draft.draft_id,
          spec_hash: draft.spec_hash,
          baseline: request.baseline,
          confirmed: true,
        },
      );
      if (controller.signal.aborted) return;
      setOutcome(response);
      add("assistant", response.explanation.join("\n"));
      setHistory(
        (old) =>
          [
            ...old,
            {
              text: request.text,
              clarifications: request.clarifications,
              outcome: "evaluated",
              summary: response.explanation.join(" ").slice(0, 1500),
            },
          ].slice(-8) as Turn[],
      );
      const spec = draft.spec;
      setSelectedSites(spec.site_ids);
      setBaseline({
        scenario_id: spec.scenario_id,
        arrival_utc: spec.arrival_utc,
        duration_hours: spec.duration_hours,
        hardware: spec.hardware,
        constraints: spec.constraints,
        min_sunlit_fraction: spec.min_sunlit_fraction,
        min_earth_los_fraction: spec.min_earth_los_fraction,
        current_site_id:
          spec.site_ids.length === 1 ? spec.site_ids[0] : spec.current_site_id,
      });
      setContext({
        rank_by: spec.rank_by,
        search_from_utc: spec.search_from_utc,
        search_until_utc: spec.search_until_utc,
      });
      setReview(null);
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Evaluation failed.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const reset = () => {
    active.current?.abort();
    setBusy(false);
    setMessages([]);
    setHistory([]);
    setReview(null);
    setPending(null);
    setOutcome(null);
    setError("");
    setText("");
    setContext({
      rank_by: "total_earth_los_hours",
      search_from_utc: null,
      search_until_utc: null,
    });
    if (caps) {
      setBaseline(createBaseline(caps));
      setSelectedSites(caps.scenario.site_ids);
    }
  };
  const cancel = () => {
    if (!review || busy) return;
    setHistory((old) =>
      [
        ...old,
        {
          text: review.request.text,
          clarifications: review.request.clarifications,
          outcome: "cancelled",
          summary: "User cancelled the interpreted request.",
        } as Turn,
      ].slice(-8),
    );
    setReview(null);
  };
  return {
    hasPending: pending !== null,
    resolveIndeterminate,
    setResolveIndeterminate,
    caps,
    error,
    baseline,
    text,
    setText,
    messages,
    review,
    busy,
    outcome,
    send,
    evaluate,
    reset,
    cancel,
  };
}
