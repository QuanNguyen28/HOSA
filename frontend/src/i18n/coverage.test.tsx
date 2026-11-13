import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import catalog from "./vi.json";
import { LanguageProvider, translate } from "./LanguageProvider";
import { CurrentStatus, MissionFields, PlanningSummary, RequestStatus, ValidationInfo } from "../figma/backend";
import { RequestDetails } from "../figma/Chat";
import { DEFAULT_MISSION, type PlanningResult, type PointResult } from "../mvp/contracts";

const uiSources = import.meta.glob<string>(["../figma/*.tsx", "../mvp/DecisionBadge.tsx", "../components/MoonScene.tsx"], { query: "?raw", import: "default", eager: true });
const technicalLabels = new Set(["HOSA", "JPL HORIZONS", "JPL_HORIZONS", "SHARED_SPICE", "m", "m DEM", "m ·"]);
const localized = (children: React.ReactNode) => renderToStaticMarkup(<LanguageProvider initialLanguage="vi">{children}</LanguageProvider>);

describe("Vietnamese display coverage", () => {
  it("requires translations for UI text, including conditional fallback branches", () => {
    const missing: string[] = [];
    for (const [file, source] of Object.entries(uiSources)) {
      const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      const check = (value: string, node: ts.Node, translated: boolean) => {
        const key = value.trim();
        if (!/[A-Za-z]{2}/.test(key) || technicalLabels.has(key)) return;
        if (!translated || !Object.hasOwn(catalog, key))
          missing.push(`${file}:${tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1}: ${key}`);
      };
      // Conditions contain machine values; only their displayed branches need translation.
      const display = (node: ts.Node, translated: boolean) => {
        if (ts.isStringLiteral(node)) check(node.text, node, translated);
        else if (ts.isConditionalExpression(node)) { display(node.whenTrue, translated); display(node.whenFalse, translated); }
        else if (ts.isParenthesizedExpression(node)) display(node.expression, translated);
        else if (ts.isBinaryExpression(node)) {
          if (node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) display(node.right, translated);
          else if ([ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)) {
            display(node.left, translated); display(node.right, translated);
          }
        }
      };
      const staticLabels = (node: ts.Node) => {
        if (ts.isStringLiteral(node)) check(node.text, node, true);
        ts.forEachChild(node, staticLabels);
      };
      const visit = (node: ts.Node) => {
        if (ts.isVariableDeclaration(node) && ["SUGGEST", "GENERAL_SUGGEST", "REQUEST_LABELS", "topics"].includes(node.name.getText(tree)) && node.initializer)
          staticLabels(node.initializer);
        if (ts.isVariableDeclaration(node) && node.name.getText(tree) === "TABS" && node.initializer && ts.isArrayLiteralExpression(node.initializer))
          for (const row of node.initializer.elements) if (ts.isArrayLiteralExpression(row) && row.elements[1]) staticLabels(row.elements[1]);
        if (ts.isPropertyAssignment(node) && node.name.getText(tree) === "label") display(node.initializer, true);
        if (ts.isJsxText(node)) check(node.text, node, false);
        if (ts.isJsxExpression(node) && node.expression && !ts.isJsxAttribute(node.parent)) display(node.expression, false);
        if (ts.isCallExpression(node) && node.expression.getText(tree) === "tr" && node.arguments[0]) display(node.arguments[0], true);
        if (ts.isJsxAttribute(node) && ["label", "title", "placeholder", "aria-label"].includes(node.name.getText(tree)) && node.initializer && ts.isStringLiteral(node.initializer))
          check(node.initializer.text, node.initializer, true);
        ts.forEachChild(node, visit);
      };
      visit(tree);
    }
    expect(missing).toEqual([]);
  });

  it("translates empty evidence, populated evidence and invalid mission fallbacks", () => {
    const empty = localized(<CurrentStatus time={0} />);
    expect(empty).toContain("Chưa có dữ liệu khoảng thời gian");
    expect(empty).not.toContain("No interval evidence");
    const result = { timeline: [], instant: { start_utc: "1970-01-01T00:00:00Z", end_utc: "1970-01-01T00:05:00Z", sun_state: "V", earth_state: "B", sun_visible_fraction: 0.75 } } as unknown as PointResult;
    const populated = localized(<CurrentStatus result={result} time={0} />);
    expect(populated).toContain("Nhìn thấy 75.0% đĩa");
    expect(populated).toContain("Khoảng thời gian từ máy chủ");
    expect(populated).not.toContain("Backend interval");
    const invalid = localized(<MissionFields mission={{ ...DEFAULT_MISSION, hours: NaN }} disabled={false} onChange={() => {}} />);
    expect(invalid).toContain("Chọn thời điểm kết thúc sau khi nhiệm vụ bắt đầu.");
    expect(invalid).not.toContain("Choose an end");
  });

  it("translates planning outcomes, structured reason lists and backend progress", () => {
    const summary = localized(<PlanningSummary result={{ result_id: "r1", status: "NO_FEASIBLE_IN_EVALUATED_SET", coverage: { candidate_total: 2, pass: 0, fail: 1, indeterminate: 1 }, apply_allowed: false, operation: "compare", candidates: [], recommended_candidate_id: null, method_version: "test", warnings: [] } satisfies PlanningResult} />);
    expect(summary).toContain("KHÔNG CÓ PHƯƠNG ÁN KHẢ THI TRONG TẬP ĐÃ ĐÁNH GIÁ");
    const validation = localized(<ValidationInfo result={{ decision: "INDETERMINATE", validation: { passed: false, reason_codes: ["INCOMPLETE_TERRAIN", "azimuth_0.25_vs_0.125:SENSITIVITY_FAILED"] } } as PointResult} />);
    expect(validation).toContain("Dữ liệu địa hình chưa đầy đủ");
    expect(validation).toContain("so sánh bước phương vị 0.25° và 0.125°: kiểm tra độ nhạy không đạt");
    expect(validation).not.toContain("SENSITIVITY_FAILED");
    const progress = localized(<RequestStatus busy stage="Completing scientific validation · revalidating seam validation 0.0625deg" error="HORIZONS_CACHE_MISS" />);
    expect(progress).toContain("kiểm chứng lại: kiểm chứng ranh giới ghép DEM, bước 0.0625°");
    expect(progress).toContain("Chưa có lịch thiên văn JPL Horizons phù hợp trong bộ nhớ đệm");
    expect(translate("horizons 5min earth batch 2 of 4", "vi")).toBe("lấy lịch thiên văn JPL Horizons cho Trái Đất theo bước 5 phút · đợt 2/4");
  });

  it("localizes request field labels while preserving site identifiers and values", () => {
    const details = localized(<RequestDetails value={{ site_ids: ["Connecting ridge", "Nobile Rim 1"], hardware: { sun_panel: 20, earth_antenna: 10 }, illumination_model: "solar_disc", data_source: "coordinate", search_until_utc: null }} />);
    expect(details).toContain("Các địa điểm đã chọn");
    expect(details).toContain("Connecting ridge, Nobile Rim 1");
    expect(details).toContain("Độ cao tấm pin · m");
    expect(details).toContain("Đĩa Mặt Trời");
    expect(details).toContain("Chưa chỉ định");
    expect(details).not.toContain("sun_panel");
  });
});
