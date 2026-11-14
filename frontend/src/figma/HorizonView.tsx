import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "../i18n/language";
import { useHorizonView } from "../hooks/useHorizonView";
import { useSkyEphemeris } from "../hooks/useSkyEphemeris";
import { sampleSky } from "../lib/skyEphemeris";
import { bearing, bearingInView, horizonAt, horizonVisibility, horizonTrackSegments } from "../lib/horizonView";
import { HorizonMarker } from './HorizonMarker';
import { currentInterval, intervalAt, type Interval, type MissionRequest, type PointResult } from "../mvp/contracts";
import type { Site } from "./model";

const COLOURS = { sun: "#ffc62b", earth: "#47afe8" };
const W = 4096, H = 640;
const plot = {left: 56, right: 980, top: 18, bottom: 346};
const buttonClass = "rounded-sm border border-line px-2 py-1.5 font-mono text-[10px] text-soft hover:border-white/50 disabled:opacity-40";

export default function HorizonView({request, site, timeMs, result, instant}: {
  request?: MissionRequest; site: Site; timeMs: number; result?: PointResult; instant?: Interval;
}) {
  const {t: tr, locale} = useTranslation();
  const {profile, profileError, track} = useHorizonView(request, result ? `${result.result_id}:${result.evaluation_status}` : undefined);
  const skyTable = useSkyEphemeris(timeMs);
  const [span, setSpan] = useState(360);
  const [centre, setCentre] = useState(180);
  const [follow, setFollow] = useState<"sun" | "earth" | null>(null);
  const [tooltip, setTooltip] = useState<number>();
  const canvas = useRef<HTMLCanvasElement>(null);
  const panorama = useRef<HTMLCanvasElement | null>(null);
  const painted = useRef<{key: string; chunks: Set<number>}>({key: "", chunks: new Set()});
  const [revision, setRevision] = useState(0);
  const clipId = useId().replaceAll(":", "");
  const coordinate = useMemo(() => ({latitude: site.lat, longitude: site.lon}), [site.lat, site.lon]);
  const elevation = profile?.coordinate.dem_z_m ?? result?.coordinate.dem_elevation_m ?? site.height_m;
  const bodies = useMemo(() => {
    if (!skyTable || !Number.isFinite(elevation) || !request) return undefined;
    const sun = sampleSky(skyTable, timeMs, coordinate, elevation + request.panel_height_m)?.sun;
    const earth = sampleSky(skyTable, timeMs, coordinate, elevation + request.antenna_height_m)?.earth;
    return sun && earth ? {sun, earth} : undefined;
  }, [skyTable, timeMs, coordinate, elevation, request?.panel_height_m, request?.antenna_height_m]);
  const sunProfile = profile?.profiles.find(p => p.height_m === request?.panel_height_m);
  const earthProfile = profile?.profiles.find(p => p.height_m === request?.antenna_height_m);
  const [profileBody, setProfileBody] = useState<"sun" | "earth">("sun");
  const shown = profileBody === "sun" ? sunProfile : earthProfile;
  const interval = (instant && intervalAt([instant],timeMs)) ?? (result && currentInterval(result, timeMs));
  const viewCentre = follow && bodies ? bodies[follow].azimuthDeg : centre;
  const minAz = viewCentre - span/2;
  const bounds = useMemo(() => {
    let low = -5, high = 15;
    for (const p of profile?.profiles ?? []) for (const point of p.points) if (point.horizon_deg != null) {
      low = Math.min(low, point.horizon_deg-1); high = Math.max(high, point.horizon_deg+1);
    }
    for (const chunk of track.chunks) for (const body of ["sun", "earth"] as const) {
      const points = chunk.bodies[body];
      for (let i=1; i<points.length; i+=3) { low = Math.min(low, points[i]-1); high = Math.max(high, points[i]+1); }
    }
    return {low: Math.floor(low/5)*5, high: Math.ceil(high/5)*5};
  }, [profile, track.chunks]);
  const x = (az: number) => plot.left + (bearingInView(az, viewCentre)-minAz)/span * (plot.right-plot.left);
  const y = (el: number) => plot.bottom - (el-bounds.low)/(bounds.high-bounds.low)*(plot.bottom-plot.top);

  // The full panorama is painted only when new trajectory chunks arrive.
  // Playback/Follow crops this bitmap rather than rebuilding every path.
  useEffect(() => {
    panorama.current ??= document.createElement("canvas");
    const surface = panorama.current;
    const context = surface.getContext("2d");
    if (!context) return;
    const key = JSON.stringify([request?.latitude_deg, request?.longitude_e_deg, request?.start_utc, request?.end_utc,
      request?.panel_height_m, request?.antenna_height_m, profile?.source_sha256, profileBody, bounds]);
    const py = (value: number) => H - (value-bounds.low)/(bounds.high-bounds.low)*H;
    if (painted.current.key !== key) {
      surface.width = W; surface.height = H;
      painted.current = {key, chunks: new Set()};
      context.clearRect(0, 0, W, H);
      context.fillStyle = "#5c5952";
      context.strokeStyle = "#b6afa1";
      context.lineWidth = 1.5;
      const hatch = document.createElement("canvas"); hatch.width=8; hatch.height=8;
      const hatchContext = hatch.getContext("2d");
      if(hatchContext){hatchContext.strokeStyle="#a58c68";hatchContext.globalAlpha=.4;hatchContext.beginPath();hatchContext.moveTo(0,8);hatchContext.lineTo(8,0);hatchContext.stroke();}
      const unknownPattern = context.createPattern(hatch,"repeat");
      if (shown) {
        // Fill contiguous sectors as one polygon; separate tiny quads leave
        // antialias seams that look like vertical stripes across the terrain.
        let active = false, firstX = 0, lastX = 0;
        const closeSector = () => {
          if (!active) return;
          context.lineTo(lastX,H); context.lineTo(firstX,H); context.closePath(); context.fill(); active = false;
        };
        for (let i=0; i<=shown.points.length; i++) {
          const point = shown.points[i%shown.points.length], px = i/shown.points.length*W;
          if (point.coverage_complete && point.horizon_deg != null) {
            if (!active) {context.beginPath(); context.moveTo(px,H); firstX=px; active=true;}
            context.lineTo(px,py(point.horizon_deg)); lastX=px;
          } else {
            closeSector();
            context.fillStyle=unknownPattern??"#8e765a33"; context.fillRect(px,0,W/shown.points.length+1,H); context.fillStyle="#5c5952";
          }
        }
        closeSector();
        context.beginPath(); active=false;
        for (let i=0; i<=shown.points.length; i++) {
          const point=shown.points[i%shown.points.length], px=i/shown.points.length*W;
          if (point.coverage_complete && point.horizon_deg != null) {
            if(active) context.lineTo(px,py(point.horizon_deg)); else context.moveTo(px,py(point.horizon_deg)); active=true;
          } else active=false;
        }
        context.stroke();
      }
    }
    for (const chunk of track.chunks) {
      if (painted.current.chunks.has(chunk.chunk_index)) continue;
      for (const body of ["sun", "earth"] as const) {
        context.strokeStyle = COLOURS[body];
        context.lineWidth = 3.5;
        const points = chunk.bodies[body], skyline = body === "sun" ? sunProfile : earthProfile;
        const segments = horizonTrackSegments(points,skyline);
        // Dashes indicate centre directions below the skyline, not a second
        // visibility decision (solar-disc fractions remain backend evidence).
        for (const visibility of ['visible', 'hidden', 'unknown'] as const) {
          context.globalAlpha = visibility === 'unknown' ? .35 : .75;
          context.setLineDash(visibility === 'hidden' ? [20,12] : visibility === 'unknown' ? [3,12] : []); context.beginPath();
          let previous: [number,number] | undefined;
          for (const segment of segments) {
            if(segment.state!==visibility) {previous=undefined;continue;}
            if(!previous || previous[0]!==segment.from[0] || previous[1]!==segment.from[1])
              context.moveTo(segment.from[0]/360*W,py(segment.from[1]));
            context.lineTo(segment.to[0]/360*W,py(segment.to[1]));
            previous=segment.to;
          }
          context.stroke();
        }
        context.setLineDash([]); context.globalAlpha = 1;
      }
      painted.current.chunks.add(chunk.chunk_index);
    }
    setRevision(value => value+1);
  }, [profile, shown, profileBody, bounds, track.chunks, request]);

  useEffect(() => {
    const target = canvas.current, surface = panorama.current;
    if (!target || !surface) return;
    const context = target.getContext("2d");
    if (!context) return;
    // SVG coordinates keep Canvas and axes aligned at every responsive width.
    target.width = 2000; target.height = 800;
    context.scale(2,2); context.clearRect(0,0,1000,400);
    const pw = plot.right-plot.left, ph = plot.bottom-plot.top;
    let drawn = 0, az = minAz;
    while (drawn < span-1e-7) {
      const normal = bearing(az), length = Math.min(360-normal, span-drawn);
      context.drawImage(surface,normal/360*W,0,length/360*W,H,
        plot.left+drawn/span*pw,plot.top,length/span*pw,ph);
      drawn += length; az += length;
    }
    // Overview strip always shows the full 360 degrees.
    context.drawImage(surface,0,0,W,H,plot.left,376,pw,20);
  }, [revision, minAz, span]);

  const zoom = (factor: number) => {
    if (bodies && follow) setCentre(bodies[follow].azimuthDeg);
    setSpan(value => Math.max(15, Math.min(360,value*factor)));
  };
  const status = (body: "sun" | "earth") => {
    const state = interval?.[`${body}_state`];
    return tr(state === "V" ? "Visible" : state === "B" ? "Hidden" : "Unknown");
  };
  const horizonTooltip = tooltip == null ? undefined : horizonAt(shown, tooltip);
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return <section aria-label={tr("Horizon panorama")} className="relative mt-[76px] flex min-h-[440px] flex-1 flex-col px-4 pb-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><h2 className="font-display text-lg text-white">{tr("Horizon · 360°")}</h2>
        <p className="font-mono text-[9px] text-mute">{tr("Terrain skyline and whole-mission Sun/Earth paths")}</p></div>
      <div className="flex flex-wrap items-center gap-1.5">
        <button className={buttonClass} aria-label={tr("Zoom out")} onClick={() => zoom(2)} disabled={span===360}>−</button>
        <button className={buttonClass} aria-label={tr("Zoom in")} onClick={() => zoom(.5)} disabled={span===15}>+</button>
        <button className={buttonClass} onClick={() => {setSpan(360);setCentre(180);setFollow(null);}}>{tr("Full 360°")}</button>
        {(["sun", "earth"] as const).map(body => <button key={body} className={buttonClass}
          aria-pressed={follow===body} style={{color: COLOURS[body],borderColor:follow===body?COLOURS[body]:undefined}}
          onClick={() => {setFollow(follow===body?null:body); if(span===360)setSpan(90);}}>
          {tr(body === "sun" ? "Follow Sun" : "Follow Earth")}</button>)}
      </div>
    </div>
    <div className="mt-2 flex flex-wrap items-center justify-between gap-1 font-mono text-[9px] text-mute">
      <span>{tr("Observer height")} · {shown?.height_m ?? request?.panel_height_m} m</span>
      {request?.panel_height_m !== request?.antenna_height_m && <select aria-label={tr("Horizon height")}
        className="border border-line bg-black px-2 py-1" value={profileBody} onChange={e=>setProfileBody(e.target.value as "sun"|"earth")}>
        <option value="sun">{tr("Sun panel")} · {request?.panel_height_m} m</option>
        <option value="earth">{tr("Earth antenna")} · {request?.antenna_height_m} m</option>
      </select>}
      <span aria-live="polite">{track.error ? tr("Unable to load all paths") : track.total && track.chunks.length===track.total ? tr("Whole mission loaded") : tr("Loading whole-mission paths…")} {track.total ? `${track.chunks.length}/${track.total}` : ""}</span>
    </div>
    {profileError && <p role="status" className="mt-2 text-[11px] text-sun">{tr("Unable to load terrain horizon.")} {tr(profileError)}</p>}
    {!profile && !profileError && <p role="status" className="mt-2 text-[11px] text-mute">{tr("Preparing terrain horizon in background…")}</p>}
    {shown && !shown.coverage_complete && <p className="text-[10px] text-sun">{tr("Hatched sectors have incomplete terrain coverage.")}</p>}
    <div className="relative mt-1 min-h-[220px] flex-1" onMouseLeave={()=>setTooltip(undefined)}>
      <canvas ref={canvas} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true" />
      <svg viewBox="0 0 1000 400" preserveAspectRatio="none" className="relative h-full w-full" role="img"
        aria-label={tr("Terrain horizon and sampled Sun/Earth tracks by azimuth and elevation")}
        onPointerMove={event => {
          const rect=event.currentTarget.getBoundingClientRect(), px=(event.clientX-rect.left)/rect.width*1000;
          setTooltip(px>=plot.left&&px<=plot.right ? bearing(minAz+(px-plot.left)/(plot.right-plot.left)*span) : undefined);
        }} onClick={event => {
          const rect=event.currentTarget.getBoundingClientRect(), px=(event.clientX-rect.left)/rect.width*1000, py=(event.clientY-rect.top)/rect.height*400;
          if(py>=376&&px>=plot.left&&px<=plot.right){setFollow(null);setCentre((px-plot.left)/(plot.right-plot.left)*360);if(span===360)setSpan(90);}
        }}>
        <defs><clipPath id={clipId}><rect x={plot.left} y={plot.top} width={plot.right-plot.left} height={plot.bottom-plot.top}/></clipPath></defs>
        {Array.from({length:5},(_,i)=>bounds.low+(bounds.high-bounds.low)*i/4).map(value=><g key={value}>
          <line x1={plot.left} x2={plot.right} y1={y(value)} y2={y(value)} stroke="#ffffff" strokeOpacity={value===0?.4:.12} strokeDasharray={value===0?"4 4":undefined}/>
          <text x={48} y={y(value)+3} textAnchor="end" fill="#a5a5a5" fontSize={12}>{value.toFixed(1)}°</text>
        </g>)}
        {Array.from({length:9},(_,i)=>minAz+span*i/8).map((az,i)=><g key={i}>
          <line x1={plot.left+(plot.right-plot.left)*i/8} x2={plot.left+(plot.right-plot.left)*i/8} y1={plot.top} y2={plot.bottom} stroke="#ffffff" strokeOpacity={.1}/>
          <text x={plot.left+(plot.right-plot.left)*i/8} y={363} textAnchor="middle" fill="#b6b6b6" fontSize={12}>{bearing(az).toFixed(0)}° {span===360?tr(directions[Math.round(bearing(az)/45)%8]):""}</text>
        </g>)}
        <g clipPath={`url(#${clipId})`}>
          {bodies && (["sun","earth"] as const).map(body=> {
            const point=bodies[body], px=x(point.azimuthDeg), py=y(point.elevationDeg);
            const horizon=horizonAt(body==="sun"?sunProfile:earthProfile,point.azimuthDeg);
            const visibility=horizonVisibility(point.elevationDeg,horizon,interval?.[`${body}_state`]);
            return <g key={body}>
              <HorizonMarker x={px} y={py} colour={COLOURS[body]} state={visibility}/>
              <text x={px+8} y={py-9} fill={COLOURS[body]} fontSize={12}>{tr(body==="sun"?"Sun":"Earth")}</text>
            </g>;
          })}
        </g>
        {bodies && (["sun","earth"] as const).map(body=><HorizonMarker key={body}
          x={plot.left+bodies[body].azimuthDeg/360*(plot.right-plot.left)} y={385} radius={3} colour={COLOURS[body]}
          state={horizonVisibility(bodies[body].elevationDeg,horizonAt(body==='sun'?sunProfile:earthProfile,bodies[body].azimuthDeg),interval?.[`${body}_state`])}/>)}
      </svg>
      {tooltip!==undefined && <div className="pointer-events-none absolute top-2 left-16 border border-line bg-black/90 p-2 font-mono text-[10px] text-soft">
        {tr("Azimuth")} {tooltip.toFixed(2)}° · {tr("Terrain horizon")} {horizonTooltip?`${horizonTooltip.elevation.toFixed(3)}°`:tr("Unknown")}
        {horizonTooltip?.distance!=null&&<div>{tr("Obstruction distance")} {(horizonTooltip.distance/1000).toFixed(2)} {tr("km")}</div>}
      </div>}
    </div>
    <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px]">
      {(["sun","earth"] as const).map(body=><span key={body} style={{color:COLOURS[body]}}>
        {tr(body==="sun"?"Sun":"Earth")} · {status(body)} · {tr("az")} {bodies?.[body].azimuthDeg.toFixed(2)??"—"}° · {tr("el")} {bodies?.[body].elevationDeg.toFixed(2)??"—"}°
      </span>)}
    </div>
    <p className="mt-1 font-mono text-[9px] text-mute">{tr("Paths cover the entire mission; sampled every")} {track.chunks[0]?`${track.chunks[0].sampling_seconds/60} ${tr("min")}`:"—"}. {tr("Directions are a geometric preview. Visibility status uses backend intervals.")} {tr("Dashed paths are below the terrain skyline.")}</p>
    <p className="font-mono text-[9px] text-mute">{request ? `${new Date(request.start_utc).toLocaleString(locale,{timeZone:"UTC"})} → ${new Date(request.end_utc).toLocaleString(locale,{timeZone:"UTC"})} UTC` : tr("Choose a valid mission range.")}</p>
  </section>;
}
