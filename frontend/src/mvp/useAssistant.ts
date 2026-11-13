import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useGroundedChat, type ChatMessage } from "./useGroundedChat";
import type { Mission } from "./contracts";

type Baseline = {
  illumination_model: "solar_disc" | "sun_center";
  scenario_id: string;
  arrival_utc: string;
  duration_hours: number;
  hardware: { sun_panel: number; earth_antenna: number };
  constraints: { max_darkness_hours: number; max_earth_blackout_hours: number };
  min_sunlit_fraction: number;
  min_earth_los_fraction: number | null;
  current_site_id: string;
  contact_requirements?: {
    min_contact_minutes: number;
    setup_minutes: number;
    required_windows: number | null;
    first_contact_deadline_minutes: number | null;
  } | null;
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
  require_explicit_start?: boolean;
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
  site_labels?: Record<string, string>;
  issues: string[];
  questions: { question: string }[];
  draft_id: string;
  spec_hash: string;
  spec: Baseline & {
    end_utc: string;
    data_source?: "snapshot" | "coordinate";
    site_ids: string[];
    rank_by: string;
    search_from_utc: string | null;
    search_until_utc: string | null;
    search_step_minutes?: number | null;
  };
};
type Evaluation = {
  site_labels?: Record<string, string>;
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
type Message = ChatMessage;

/** Working baseline for a new planning conversation. With the tabs' shared
 * mission settings, chat uses the same heights, sunlight threshold, contact
 * requirements and soft limits as Explore/Compare/Best dates (no Earth LOS
 * fraction unless the user asks for one), so the same question gives the same
 * engine result in chat and in the tabs. */
/** No site is preselected: the user names one of the 27 tab sites. */
const DEFAULT_CHAT_SITE = "connecting-ridge";

function createBaseline(c: Capabilities, mission?: Mission): Baseline {
  const base: Baseline = {
    illumination_model: "solar_disc",
    scenario_id: c.scenario.scenario_id,
    arrival_utc: c.scenario.A_utc,
    duration_hours: c.scenario.D_hours,
    hardware: c.scenario.device_heights_m,
    constraints: c.scenario.example_constraints,
    ...c.scenario.example_requirements,
    current_site_id: c.scenario.site_ids[0],
  };
  if (!mission) return base;
  return {
    ...base,
    // First of the 27 tab sites; chat never defaults to the archived P1 observers.
    current_site_id: DEFAULT_CHAT_SITE,
    hardware: { sun_panel: mission.panel, earth_antenna: mission.antenna },
    constraints: { max_darkness_hours: mission.darkness, max_earth_blackout_hours: mission.blackout },
    min_sunlit_fraction: mission.sun / 100,
    min_earth_los_fraction: null,
    contact_requirements: mission.contact > 0
      ? {
          min_contact_minutes: mission.contact,
          setup_minutes: mission.setup,
          required_windows: mission.windows || null,
          first_contact_deadline_minutes: mission.deadline || null,
        }
      : null,
  };
}

export function useAssistant(mission?: Mission) {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [mode, setMode] = useState<"general" | "planning">("general");
  const general = useGroundedChat(caps?.assistant_enabled === true);
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
  // Name + coordinates for site IDs seen in this conversation (two sites can share a region name).
  const [siteLabels, setSiteLabels] = useState<Record<string, string>>({});
  const [resolveIndeterminate, setResolveIndeterminate] = useState(true);
  const [outcome, setOutcome] = useState<Evaluation | null>(null);
  const active = useRef<AbortController | null>(null);
  const missionRef = useRef(mission);
  missionRef.current = mission;
  useEffect(() => {
    const controller = new AbortController();
    api<Capabilities>("/assistant/capabilities", controller.signal)
      .then((c) => {
        setCaps(c);
        setBaseline(createBaseline(c, missionRef.current));
        setSelectedSites([]);
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
  // Before the first evaluated turn, follow edits to the tabs' mission settings.
  // Later turns keep the conversation's own working baseline.
  useEffect(() => {
    if (caps && history.length === 0 && !pending && !review)
      setBaseline(createBaseline(caps, mission));
  }, [caps, mission, history.length, pending, review]);
  const add = (who: Message["who"], value: string) =>
    setMessages((old) => [...old, { who, text: value }]);
  const sendPlanning = async (input: string, fromGeneral = false) => {
    if (!baseline || !caps?.assistant_enabled || busy || review || !input.trim())
      return;
    const answer = input.trim();
    setText("");
    setError("");
    setOutcome(null);
    add("user", answer);
    setBusy(true);
    const controller = new AbortController();
    active.current = controller;
    const request: ParseRequest = pending && !fromGeneral
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
          // The first planning request must name its start (or a search
          // range); only follow-ups may inherit the previous evaluated start.
          require_explicit_start: fromGeneral || history.length === 0,
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
        // Keep the request for unsupported parts too, so "drop that part"
        // continues this request instead of starting an empty one.
        setPending(request);
      }
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Unable to parse request.");
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const send = async () => {
    if (mode === "planning") {
      await sendPlanning(text);
      return;
    }
    const prompt = general.text.trim();
    const completed = await general.send();
    if (completed?.result?.next_action !== "prepare_mission") return;
    setMode("planning");
    if (busy || review) {
      // Keep an outstanding calculation or review intact.
      setText(prompt);
      return;
    }
    await sendPlanning(prompt, true);
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
      setOutcome({ ...response, site_labels: draft.site_labels });
      setSiteLabels((old) => ({ ...old, ...draft.site_labels }));
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
        illumination_model: spec.illumination_model,
        scenario_id: spec.scenario_id,
        arrival_utc: spec.arrival_utc,
        duration_hours: spec.duration_hours,
        hardware: spec.hardware,
        constraints: spec.constraints,
        min_sunlit_fraction: spec.min_sunlit_fraction,
        min_earth_los_fraction: spec.min_earth_los_fraction,
        current_site_id: spec.site_ids.length === 1 ? spec.site_ids[0] : spec.current_site_id,
        contact_requirements: spec.contact_requirements ?? null,
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
      setBaseline(createBaseline(caps, missionRef.current));
      setSelectedSites([]);
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
    siteLabels,
    hasHistory: history.length > 0,
    resolveIndeterminate,
    setResolveIndeterminate,
    caps,
    mode,
    setMode,
    error: mode === "general" ? general.error || (!caps ? error : "") : error,
    baseline,
    text: mode === "general" ? general.text : text,
    setText: mode === "general" ? general.setText : setText,
    messages: mode === "general" ? general.messages : messages,
    review: mode === "general" ? null : review,
    busy: mode === "general" ? general.busy : busy,
    outcome: mode === "general" ? null : outcome,
    run: mode === "general" ? general.run : null,
    stop: general.stop,
    send,
    evaluate,
    reset: mode === "general" ? general.reset : reset,
    cancel,
  };
}
