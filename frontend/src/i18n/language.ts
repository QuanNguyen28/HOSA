import { useCallback, useContext } from "react";
import vietnamese from "./vi.json";
import { LanguageContext } from "./languageContext";

export type Language = "en" | "vi";
export const LANGUAGE_STORAGE_KEY = "hosa.language";
const catalog: Record<string, string> = vietnamese;

function interpolate(template: string, values: readonly unknown[], language: Language): string {
  return template.replace(/\{(\d+)\}/g, (token, index: string) =>
    Number(index) < values.length ? String(translate(values[Number(index)], language)) : token,
  );
}

// These also cover formatted validation/progress messages received from shared code.
const sharedMessageTemplates = new Set([
  "{0} must be between {1} and {2}.",
  "{0} must be a finite number of at least {1}.",
  "API request failed ({0}).",
  "Completing scientific validation · {0}",
  "refining horizon {0}",
  "revalidating {0}",
  "refining horizon {0}deg",
  "revalidating {0} {1}deg",
  "horizons {0}min {1} batch {2} of {3}",
  "shared ephemeris {0}min {1}",
  "horizons {0}min",
  "{0}:COMPARISON_EVIDENCE_MISSING",
  "{0}:SENSITIVITY_FAILED",
  "azimuth_{0}_vs_{1}",
]);
const messagePatterns = Object.entries(catalog)
  .filter(([key]) => sharedMessageTemplates.has(key))
  .sort(([a], [b]) => b.replace(/\{\d+\}/g, "").length - a.replace(/\{\d+\}/g, "").length)
  .map(([key, value]) => ({
    pattern: key === "revalidating {0} {1}deg" ? /^revalidating (.+) ([\d.]+)deg$/ : new RegExp(`^${key.split(/\{\d+\}/).map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("(.+?)")}$`),
    value,
  }));

/** Translate display strings only; numeric values, React elements and domain data pass through. */
export function translate<T>(value: T, language: Language, values?: readonly unknown[]): T {
  if (typeof value !== "string") return value;
  const key = value.trim();
  if (!key) return value;
  const known = Object.hasOwn(catalog, key);
  let text = language === "vi" && known ? catalog[key] : key;
  if (values) text = interpolate(text, values, language);
  else if (language === "vi" && !known) {
    for (const { pattern, value: template } of messagePatterns) {
      const match = pattern.exec(key);
      if (match) {
        text = interpolate(template, match.slice(1), language);
        break;
      }
    }
  }
  return (value.slice(0, value.length - value.trimStart().length) + text + value.slice(value.trimEnd().length)) as T;
}

export function readLanguage(): Language {
  try {
    return typeof window !== "undefined" && window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === "vi" ? "vi" : "en";
  } catch {
    return "en";
  }
}

export function useTranslation() {
  const context = useContext(LanguageContext);
  const t = useCallback(<T,>(value: T, values?: readonly unknown[]) => translate(value, context.language, values), [context.language]);
  return { ...context, t, locale: context.language === "vi" ? "vi-VN" : "en-GB" };
}
