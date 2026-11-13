import { createContext, type Context } from "react";
import type { Language } from "./language";

export type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
};

type HotData = { hosaLanguageContext?: Context<LanguageContextValue> };

/** Keep providers and consumers on the same context across development module updates. */
export function contextForHotData(data?: HotData): Context<LanguageContextValue> {
  const context = data?.hosaLanguageContext ?? createContext<LanguageContextValue>({ language: "en", setLanguage: () => {} });
  if (data) data.hosaLanguageContext = context;
  return context;
}

export const LanguageContext = contextForHotData(import.meta.hot?.data);
