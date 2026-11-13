import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { LanguageProvider } from "./LanguageProvider";
import { LANGUAGE_STORAGE_KEY, readLanguage, translate } from "./language";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MissionFields, ValidationInfo } from "../figma/backend";
import { ChatThread, type Assistant } from "../figma/Chat";
import { SITES } from "../figma/model";
import { DEFAULT_MISSION, missionIssue, type PointResult } from "../mvp/contracts";

afterEach(() => vi.unstubAllGlobals());

describe("language preference", () => {
  it("restores Vietnamese and falls back to English for missing or invalid preferences", () => {
    const getItem = vi.fn().mockReturnValue("vi");
    vi.stubGlobal("window", { localStorage: { getItem } });
    expect(readLanguage()).toBe("vi");
    expect(getItem).toHaveBeenCalledWith(LANGUAGE_STORAGE_KEY);
    for (const value of [null, "en", "fr", ""]) {
      getItem.mockReturnValue(value);
      expect(readLanguage()).toBe("en");
    }
  });

  it("works when storage is blocked or when rendering without a browser", () => {
    vi.stubGlobal("window", { get localStorage() { throw new Error("Storage blocked"); } });
    expect(readLanguage()).toBe("en");
    vi.stubGlobal("window", undefined);
    expect(readLanguage()).toBe("en");
  });
});

describe("localized mission UI", () => {
  it("preserves every official site name in both languages", () => {
    for (const site of SITES) {
      expect(translate(site.name, "vi")).toBe(site.name);
      expect(translate(site.name, "en")).toBe(site.name);
    }
  });

  it("translates shared validation messages while retaining the actual limits", () => {
    const issue = missionIssue({ ...DEFAULT_MISSION, panel: 31 });
    expect(translate(issue, "en")).toBe("Panel height must be between 0.01 and 30.");
    expect(translate(issue, "vi")).toBe("Độ cao tấm pin phải nằm trong khoảng 0.01 đến 30.");
    expect(translate("Completing scientific validation · refining horizon 2", "vi"))
      .toBe("Đang hoàn tất kiểm chứng khoa học · đang tinh chỉnh đường chân trời 2");
    expect(translate(" ", "vi")).toBe(" ");
    expect(translate("NASA_LOLA_5M", "vi")).toBe("NASA_LOLA_5M");
  });

  it("renders the selected flag, mission fields and numerical evidence in Vietnamese", () => {
    const result = {
      decision: "FAIL", validation: { passed: false },
      hard_failure: {
        constraint: "min_sunlit_fraction", limit: 0.8, observed_bounds: [0, 0],
        shortfall_hours_bounds: [57.6, 57.6],
        window: { start_utc: "2026-11-17T00:00:00Z", end_utc: "2026-11-20T00:00:00Z" },
        explanation: "", evidence_intervals: [],
      },
    } as unknown as PointResult;
    const html = renderToStaticMarkup(
      <LanguageProvider initialLanguage="vi">
        <LanguageSwitcher />
        <MissionFields mission={DEFAULT_MISSION} disabled={false} onChange={() => {}} />
        <ValidationInfo result={result} />
      </LanguageProvider>,
    );
    expect(html).toContain('aria-label="Tiếng Việt" title="Tiếng Việt" aria-pressed="true"');
    expect(html).toContain('transform:translateX(100%)');
    expect(html).toContain("Yêu cầu nhiệm vụ");
    expect(html).toContain("Không đạt yêu cầu bắt buộc:");
    expect(html).toContain("Yêu cầu 80.00%; cận trên 0.00%");
    expect(html).toContain("2026-11-17 00:00:00Z");
    expect(html).not.toContain("Mission requirements");
  });

  it("localizes assistant controls and suggestions while preserving conversation and source evidence", () => {
    const assistant = {
      messages: [
        { who: "user", text: "Compare sites" },
        { who: "assistant", text: "Numerical checks passed", citations: [{ source_id: "s1", path: "docs/evidence.md", excerpt: "Mean visible Sun disc" }] },
      ],
      busy: false, review: null, outcome: null, baseline: null, caps: { assistant_enabled: true },
      error: "", mode: "general", run: null, text: "", setMode: () => {},
    } as unknown as Assistant;
    const html = renderToStaticMarkup(<LanguageProvider initialLanguage="vi"><ChatThread a={assistant} /></LanguageProvider>);
    expect(html).toContain("Trò chuyện chung");
    expect(html).toContain("Gửi");
    expect(html).toContain("Compare sites");
    expect(html).toContain("Numerical checks passed");
    expect(html).toContain("Mean visible Sun disc");
    assistant.messages = [];
    const english = renderToStaticMarkup(<LanguageProvider initialLanguage="en"><ChatThread a={assistant} /></LanguageProvider>);
    expect(english).toContain("How does INDETERMINATE differ from FAIL?");
    expect(english).not.toContain("khác FAIL");
  });
});
