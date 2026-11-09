import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownToLine,
  CheckCircle2,
  Clock3,
  Database,
  Radio,
  RefreshCw,
  Sun,
} from "lucide-react";

import { useHorizonProfile, usePlanning, type PlanningEvent, type SitePlan } from "../hooks/usePlanning";
import type { Site } from "../types";

type Props = { sites: Site[] };

const decisionLabel = {
  PASS: "ĐẠT",
  FAIL: "KHÔNG ĐẠT",
  INDETERMINATE: "CHƯA XÁC ĐỊNH",
};

function utcAt(start: string, index: number, minutes: number) {
  return new Date(new Date(start).getTime() + index * minutes * 60_000);
}

function shortUtc(value: string | Date) {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "UTC",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date).replace(",", "") + " UTC";
}

function metric(pair: [number, number]) {
  return Math.abs(pair[1] - pair[0]) < 1e-8
    ? `${pair[1].toFixed(2)} h`
    : `${pair[0].toFixed(2)}–${pair[1].toFixed(2)} h`;
}

function Timeline({ site }: { site: SitePlan }) {
  const start = new Date(site.start_utc).getTime();
  const duration = new Date(site.end_utc).getTime() - start;
  return (
    <div className="comparison-timeline" aria-label={`Timeline ${site.site_id}`}>
      <div className="timeline-lane">
        <span className="lane-label"><Sun size={12} /> SUN</span>
        <div className="lane-track">
          {site.events.filter((event) => event.body === "sun").map((event, index) => (
            <EventBar key={`${event.start_utc}-${index}`} event={event} start={start} duration={duration} />
          ))}
        </div>
      </div>
      <div className="timeline-lane">
        <span className="lane-label"><Radio size={12} /> EARTH</span>
        <div className="lane-track">
          {site.events.filter((event) => event.body === "earth").map((event, index) => (
            <EventBar key={`${event.start_utc}-${index}`} event={event} start={start} duration={duration} />
          ))}
        </div>
      </div>
      <div className="timeline-ticks"><span>0 h</span><span>24 h</span><span>48 h</span><span>72 h</span></div>
    </div>
  );
}

function EventBar({ event, start, duration }: { event: PlanningEvent; start: number; duration: number }) {
  const left = ((new Date(event.start_utc).getTime() - start) / duration) * 100;
  const width = ((new Date(event.end_utc).getTime() - new Date(event.start_utc).getTime()) / duration) * 100;
  return (
    <span
      className={`event-bar event-${event.state === "B" ? "blocked" : "unknown"}`}
      style={{ left: `${Math.max(0, left)}%`, width: `${Math.min(100 - left, width)}%` }}
      title={`${event.state === "B" ? "Blocked" : "Unknown"}: ${event.duration_hours.toFixed(2)} h`}
    />
  );
}

function SiteResultCard({ site, name, active, onSelect, onExplain }: {
  site: SitePlan;
  name: string;
  active: boolean;
  onSelect: () => void;
  onExplain: (body: "sun" | "earth") => void;
}) {
  const decisive = site.decisive_event;
  return (
    <article className={`site-result-card ${active ? "active" : ""}`} onClick={onSelect}>
      <header>
        <div><span>{site.site_id}</span><h3>{name}</h3></div>
        <strong className={`decision decision-${site.decision.toLowerCase()}`}>{decisionLabel[site.decision]}</strong>
      </header>
      <div className="constraint-row">
        <div><Sun size={14} /><span>Tối liên tục</span><strong>{metric(site.metrics.longest_dark_hours)}</strong></div>
        <b className={`check check-${site.constraint_states.max_darkness_hours.toLowerCase()}`}>{decisionLabel[site.constraint_states.max_darkness_hours]}</b>
      </div>
      <div className="constraint-row">
        <div><Radio size={14} /><span>Mất Earth LOS</span><strong>{metric(site.metrics.longest_blackout_hours)}</strong></div>
        <b className={`check check-${site.constraint_states.max_earth_blackout_hours.toLowerCase()}`}>{decisionLabel[site.constraint_states.max_earth_blackout_hours]}</b>
      </div>
      <Timeline site={site} />
      <div className="metric-strip">
        <div><span>TỔNG GIỜ SUN</span><strong>{metric(site.metrics.total_sun_hours)}</strong></div>
        <div><span>ĐỒNG THỜI DÀI NHẤT</span><strong>{metric(site.metrics.longest_joint_hours)}</strong></div>
      </div>
      <div className={`sensitivity-strip sensitivity-${site.sensitivity.status.toLowerCase()}`}>
        <span>NUMERICAL SENSITIVITY</span>
        <strong>{site.sensitivity.status === "STABLE_DECISION" ? "DECISION STABLE" : site.sensitivity.status.replace("_", " ")}</strong>
        {site.sensitivity.max_duration_difference_minutes != null && (
          <small>
            1-min Δduration ≤ {site.sensitivity.max_duration_difference_minutes.toFixed(1)} min ·
            Δevent ≤ {site.sensitivity.max_event_shift_minutes?.toFixed(1) ?? "—"} min
            {site.sensitivity.angular_sensitive ? " · angular profile flagged" : ""}
          </small>
        )}
      </div>
      {decisive ? (
        <button
          className="decisive-event"
          onClick={(clickEvent) => {
            clickEvent.stopPropagation();
            onExplain(decisive.body);
          }}
          aria-label={`Explain ${decisive.body} blockage on the horizon profile`}
        >
          <AlertTriangle size={14} />
          <p>
            <strong>Sự kiện quyết định</strong>
            {decisive.body === "earth" ? "Earth bị địa hình che" : "Sun bị địa hình che"} trong {decisive.duration_hours.toFixed(2)} giờ,
            từ {shortUtc(decisive.start_utc)}. Khoảng hở xấu nhất {decisive.worst_sample.clearance_deg?.toFixed(2) ?? "—"}°.
          </p>
        </button>
      ) : (
        <div className="decisive-event positive"><CheckCircle2 size={14} /><p>Không có sự kiện chặn làm vượt ngưỡng đã chọn.</p></div>
      )}
    </article>
  );
}

function HorizonChart({ siteId, target, event }: {
  siteId: string;
  target: "sun" | "earth";
  event: PlanningEvent | null;
}) {
  const { profile, error } = useHorizonProfile(siteId, target);
  const points = useMemo(() => profile?.points.filter((_, index) => index % 4 === 0) ?? [], [profile]);
  const values = points.map((point) => point.horizon_deg);
  const min = Math.min(-5, ...values);
  const max = Math.max(5, ...values);
  const polyline = points.map((point) => {
    const x = point.azimuth_deg / 360 * 1000;
    const y = 170 - ((point.horizon_deg - min) / (max - min || 1)) * 140;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const sample = event?.body === target ? event.worst_sample : null;
  const sampleX = sample?.azimuth_deg != null ? sample.azimuth_deg / 360 * 1000 : null;
  const sampleY = sample?.elevation_deg != null ? 170 - ((sample.elevation_deg - min) / (max - min || 1)) * 140 : null;
  return (
    <section className="horizon-panel">
      <header>
        <div><span>HORIZON PROFILE</span><strong>{siteId} · {target === "sun" ? "PANEL 1 m" : "ANTENNA 2 m"}</strong></div>
        <small>{profile ? `${profile.azimuth_step_deg}° · ${profile.coverage_complete ? "100% covered" : "partial"}` : error ?? "Loading…"}</small>
      </header>
      <svg viewBox="0 0 1000 190" preserveAspectRatio="none" role="img" aria-label="Terrain horizon by azimuth">
        <line x1="0" x2="1000" y1="170" y2="170" className="chart-axis" />
        <line x1="0" x2="1000" y1="100" y2="100" className="chart-grid" />
        <polyline points={polyline} className="horizon-line" />
        {sampleX !== null && sampleY !== null && <circle cx={sampleX} cy={sampleY} r="7" className="body-marker" />}
      </svg>
      <div className="az-labels"><span>0° N</span><span>90° E</span><span>180° S</span><span>270° W</span><span>360°</span></div>
    </section>
  );
}

export function CompareWorkspace({ sites }: Props) {
  const { scenario, result, loading, error, analyze } = usePlanning();
  const [startIndex, setStartIndex] = useState(0);
  const [darkness, setDarkness] = useState(12);
  const [blackout, setBlackout] = useState(6);
  const [activeSiteId, setActiveSiteId] = useState("Site01_P1");
  const [target, setTarget] = useState<"sun" | "earth">("earth");

  useEffect(() => {
    if (scenario && !result && !loading) void analyze(0, 12, 6);
  }, [scenario, result, loading, analyze]);

  const selectedResult = result?.sites.find((site) => site.site_id === activeSiteId) ?? result?.sites[0] ?? null;
  const startUtc = scenario ? utcAt(scenario.A_utc, startIndex, scenario.start_step_minutes) : null;
  const run = () => void analyze(startIndex, darkness, blackout);

  return (
    <section className="compare-workspace" aria-label="Lunar site comparison workspace">
      <aside className="scenario-panel glass-panel">
        <div className="compare-eyebrow"><Database size={13} /> SCENARIO</div>
        <h2>Hoạt động 72 giờ</h2>
        <p>So sánh hai điểm trên cùng dữ liệu, mốc UTC và quy tắc hình học.</p>
        <label className="field-label">MỐC BẮT ĐẦU · LƯỚI 15 PHÚT</label>
        <div className="start-index-row">
          <button onClick={() => setStartIndex((value) => Math.max(0, value - 1))}>−</button>
          <div><strong>{startUtc ? shortUtc(startUtc) : "Loading…"}</strong><span>index {startIndex} / 1343</span></div>
          <button onClick={() => setStartIndex((value) => Math.min(1343, value + 1))}>+</button>
        </div>
        <input
          type="range"
          min="0"
          max="1343"
          step="1"
          value={startIndex}
          aria-label="Start index"
          onChange={(event) => setStartIndex(Number(event.target.value))}
        />
        <div className="constraint-inputs">
          <label><span>TỐI TỐI ĐA</span><div><input type="number" min="0" max="72" step="0.25" value={darkness} onChange={(event) => setDarkness(Number(event.target.value))} /><b>h</b></div></label>
          <label><span>MẤT EARTH LOS TỐI ĐA</span><div><input type="number" min="0" max="72" step="0.25" value={blackout} onChange={(event) => setBlackout(Number(event.target.value))} /><b>h</b></div></label>
        </div>
        <button className="run-analysis" onClick={run} disabled={!scenario || loading}>
          <RefreshCw size={14} className={loading ? "spin" : ""} /> {loading ? "ĐANG PHÂN TÍCH" : "PHÂN TÍCH HAI ĐIỂM"}
        </button>
        {error && <p className="analysis-error">{error}</p>}
        <dl className="scenario-meta">
          <div><dt>MÔ HÌNH</dt><dd>{scenario?.model_step_minutes ?? "—"} phút</dd></div>
          <div><dt>PANEL / ANTENNA</dt><dd>{scenario ? `${scenario.device_heights_m.sun_panel} / ${scenario.device_heights_m.earth_antenna} m` : "—"}</dd></div>
          <div><dt>TRẠNG THÁI</dt><dd>{scenario?.status ?? "—"}</dd></div>
        </dl>
      </aside>

      <div className="comparison-main">
        <header className="comparison-heading">
          <div><span>MISSION WINDOW COMPARISON</span><h1>So sánh điều kiện tại cực nam Mặt Trăng</h1></div>
          {result && (
            <div className="export-actions">
              <a href={`/api/results/${result.result_id}/export?format=json`} download><ArrowDownToLine size={13} /> JSON</a>
              <a href={`/api/results/${result.result_id}/export?format=csv`} download><ArrowDownToLine size={13} /> CSV</a>
            </div>
          )}
        </header>
        <div className="site-comparison-grid">
          {result?.sites.map((site) => (
            <SiteResultCard
              key={site.site_id}
              site={site}
              name={sites.find((item) => item.id === site.site_id)?.name ?? site.site_id}
              active={activeSiteId === site.site_id}
              onSelect={() => setActiveSiteId(site.site_id)}
              onExplain={(body) => {
                setActiveSiteId(site.site_id);
                setTarget(body);
                requestAnimationFrame(() => document.getElementById("horizon-evidence")?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
              }}
            />
          )) ?? <div className="comparison-loading"><Clock3 size={18} /> Đang đọc dữ liệu đã kiểm định…</div>}
        </div>
        {selectedResult && (
          <div className="evidence-section" id="horizon-evidence">
            <div className="evidence-tabs">
              <button className={target === "sun" ? "active" : ""} onClick={() => setTarget("sun")}><Sun size={13} /> SUN HORIZON</button>
              <button className={target === "earth" ? "active" : ""} onClick={() => setTarget("earth")}><Radio size={13} /> EARTH HORIZON</button>
            </div>
            <HorizonChart siteId={selectedResult.site_id} target={target} event={selectedResult.decisive_event} />
          </div>
        )}
        <footer className="model-disclaimer">
          <AlertTriangle size={13} /> Earth LOS là điều kiện hình học tới tâm Trái Đất; Sun visibility không phải mô hình điện hoặc nhiệt. Kết quả PROVISIONAL, không phải chứng nhận hạ cánh.
        </footer>
      </div>
    </section>
  );
}

