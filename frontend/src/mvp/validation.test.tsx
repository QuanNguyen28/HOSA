import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ValidationInfo, BackendTimeline, CurrentStatus } from "../figma/backend";
import type { PointResult } from "./contracts";
import { LiveBar } from "../figma/ui";

describe("hard-first explanation", () => {
  it("shows the failed threshold and evidence dates without claiming validation ran", () => {
    const result = { decision: "FAIL", validation: { passed: false, status: "skipped_hard_failure" }, hard_failure: {
      constraint: "min_sunlit_fraction", limit: .8, observed_bounds: [0, 0], shortfall_hours_bounds: [57.6, 57.6],
      window: { start_utc: "2026-11-17T00:00:00Z", end_utc: "2026-11-20T00:00:00Z" },
      explanation: "Whole-window shortfall.", evidence_intervals: [{ target: "sun", start_utc: "2026-11-17T00:00:00Z", end_utc: "2026-11-18T00:00:00Z" }],
    } } as unknown as PointResult;
    const html = renderToStaticMarkup(<ValidationInfo result={result} onTime={() => {}} />);
    expect(html).toContain("Required 80.00%; upper bound 0.00%");
    expect(html).toContain("Validation and soft preferences skipped");
    expect(html).toContain("2026-11-17 00:00:00Z");
    expect(html).not.toContain("Validation incomplete or failed");
    result.hard_failure!.confirmed_sampling_minutes = [5, 1];
    const confirmed = renderToStaticMarkup(<ValidationInfo result={result} />);
    expect(confirmed).toContain("Hard failure confirmed on 5/1-minute grids");
    expect(confirmed).toContain("Full validation and soft preferences skipped");
  });
});

describe("prepared preview charts", () => {
  it("shows known averages in color and uncertain bounds as hatching", () => {
    const start = Date.parse("2026-11-17T00:00:00Z"), end = start+3600000;
    const result = { timeline: [{ start_utc: new Date(start).toISOString(), end_utc: new Date(end).toISOString(),
      aggregated: true, sun_state: "?", earth_state: "?", joint_state: "?",
      sun_visible_fraction_lower: .5, sun_visible_fraction_upper: .5,
      earth_visible_fraction_lower: .75, earth_visible_fraction_upper: .75,
      joint_visible_fraction_lower: .25, joint_visible_fraction_upper: .75,
    }], timeline_transport: { mode: "aggregated", exact_intervals_ready: false } } as unknown as PointResult;
    const html = renderToStaticMarkup(<BackendTimeline result={result} start={start} end={end} time={start} onTime={() => {}} />);
    expect(html).toContain("height:50%");
    expect(html).toContain("height:75%");
    expect(html).toContain("background:#06B6D4");
    expect(html).toContain("repeating-linear-gradient");
    expect(html).toContain("75% visible time in display bin");
    result.timeline[0].joint_visible_fraction_lower = .75001;
    result.timeline[0].joint_visible_fraction_upper = .75002;
    const rounded = renderToStaticMarkup(<BackendTimeline result={result} start={start} end={end} time={start} onTime={() => {}} />);
    expect(rounded).not.toContain("75–75");
    expect(rounded).toContain("repeating-linear-gradient");
  });
});

describe("instant visibility", () => {
  it('shows a prepared instant without requiring aggregate metrics or Analyze', () => {
    const instant={start_utc:'2026-11-24T00:00:00Z',end_utc:'2026-11-24T00:05:00Z',sun_state:'V',earth_state:'B',joint_state:'B',sun_visible_fraction:1,evidence_source:'prepared_nominal'} as const;
    const html=renderToStaticMarkup(<CurrentStatus instant={instant} time={Date.parse(instant.start_utc)}/>);
    expect(html).toContain('Sun');expect(html).toContain('visible');expect(html).toContain('blocked');
    expect(html).not.toContain('No interval evidence');expect(html).not.toContain('unknown');
  });
  it("offers Continue plus Replay while paused, and only Replay at the final minute", () => {
    const start = Date.parse("2026-01-27T00:00:00Z");
    const s = { startMs: start, endMs: start+72*3600000, timeMs: start+60000,
      playing: false, speed: 24, dark: 0, margin: 0, hIdx: 2 };
    const render = () => renderToStaticMarkup(<LiveBar s={s} setTime={() => {}} setPlaying={() => {}} setSpeed={() => {}} setRange={() => {}} />);
    const paused = render();
    expect(paused).toContain('aria-label="Continue"');
    expect(paused).toContain('aria-label="Replay"');
    s.timeMs = s.endMs-60000;
    const complete = render();
    expect(complete).toContain('aria-label="Replay"');
    expect(complete).not.toContain('aria-label="Continue"');
    expect(complete).not.toContain('aria-label="Play"');
    s.timeMs = start;
    expect(render()).toContain('aria-label="Play"');
    expect(render()).not.toContain('aria-label="Replay"');
  });
  it("keeps a 07:16 evidence seek on the one-minute slider and includes the last mission minute", () => {
    const start = Date.parse("2026-01-27T00:00:00Z");
    const html = renderToStaticMarkup(<LiveBar s={{ startMs: start, endMs: start+72*3600000,
      timeMs: start+436*60000, playing: false, speed: 24, dark: 0, margin: 0, hIdx: 2 }}
      setTime={() => {}} setPlaying={() => {}} setSpeed={() => {}} setRange={() => {}} />);
    expect(html).toContain('min="0"');
    expect(html).toContain('max="4319"');
    expect(html).toContain('step="1"');
    expect(html).toContain('value="436"');
    expect(html).toContain('07:16:00');
  });
  it("does not round a positive partial Sun disc to a misleading zero or full disc", () => {
    const result = { timeline: [], instant: { start_utc: "2026-11-17T00:00:00Z", end_utc: "2026-11-17T00:05:00Z",
      sun_state: "V", earth_state: "V", joint_state: "V", sun_visible_fraction: .0000560892 } } as unknown as PointResult;
    const time = Date.parse(result.instant!.start_utc);
    const html = renderToStaticMarkup(<CurrentStatus result={result} time={time} />);
    expect(html).toContain("Sun partly visible");
    expect(html).toContain("&lt;0.1% of disc visible");
    expect(html).not.toContain("0.0% of disc visible");
    result.instant!.sun_visible_fraction = .99999;
    const almost = renderToStaticMarkup(<CurrentStatus result={result} time={time} />);
    expect(almost).toContain("&gt;99.9% of disc visible");
    expect(almost).not.toContain("100.0% of disc visible");
  });
  it("discards a stale visible instant at its end and uses the blocked native interval", () => {
    const start = Date.parse("2026-11-17T00:00:00Z");
    const instant = { start_utc: new Date(start).toISOString(), end_utc: new Date(start+300000).toISOString(),
      sun_state: "V", earth_state: "V", joint_state: "V", sun_visible_fraction: .5 };
    const result = { instant, timeline: [{ ...instant, start_utc: instant.end_utc, end_utc: new Date(start+600000).toISOString(),
      sun_state: "B", earth_state: "B", joint_state: "B", sun_visible_fraction: 0 }] } as PointResult;
    const html = renderToStaticMarkup(<CurrentStatus result={result} time={start+300000} />);
    expect(html).toContain("Sun blocked");
    expect(html).toContain("Earth blocked");
    expect(html).toContain("0.0% of disc visible");
    expect(html).not.toContain("50.0%");
    result.timeline = [];
    const missing = renderToStaticMarkup(<CurrentStatus result={result} time={start+300000} />);
    expect(missing).toContain("Sun unknown");
    expect(missing).toContain("Earth unknown");
  });
});
