import os, shutil, subprocess, sys, traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
import numpy as np
import pandas as pd
from .acquire import VERSION, REGIONS, dump, load, download, environment, inventory, sources, utc_now
from .terrain import DEM, R, raster_stats, choose_site, site_geojson, raster_figure
from .horizons import fetch
from .horizon import profile, seam_diagnostics, reference_check
from .visibility import visibility, lookup, grid_windows, sensitivity, analyze

def stage(state,key,status,detail=None,**more):
    state[key]={"status":status,**({"detail":detail} if detail else {}),**more}
    print(key,status,detail or "",flush=True)

def csvout(root,path,df,index=False):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(p,index=index,date_format="%Y-%m-%dT%H:%M:%SZ")
    return p

def select_sources(nasa_dir,items,ids,offline):
    wanted=[i for i in items if i["id"] in ids]
    def attempt(item):
        try: return download(nasa_dir,item,offline)
        except Exception as e: return dict(item,status="BLOCKED" if isinstance(e,(FileNotFoundError,OSError)) or type(e).__name__ in {"ConnectionError","ReadTimeout","ConnectTimeout"} else "FAIL",reason=f"{type(e).__name__}: {e}")
    with ThreadPoolExecutor(max_workers=3) as pool:
        return {rec["id"]:rec for rec in pool.map(attempt,wanted)}

def plot_ephem(root,site,s,e):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,1,figsize=(11,6),sharex=True,layout="constrained")
    for label,data,color in [("Sun centre",s,"#b45d11"),("Earth centre",e,"#286b94")]:
        axs[0].plot(data.index,data.el_deg,label=label,color=color)
        axs[1].scatter(data.index,data.az_deg,label=label,color=color,s=1.6)
    axs[0].axhline(0,color=".5",lw=.8);axs[0].legend();axs[0].set_ylabel("Elevation (°)")
    axs[1].set(ylabel="Azimuth (° east of north)",xlabel="UTC",ylim=(-5,365))
    fig.suptitle(f"{site} • JPL Horizons • PROVISIONAL scenario")
    fig.savefig(root/"figures"/f"{site}_horizons.png",dpi=140);plt.close(fig)

def plot_horizon(root,site,allp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,4),layout="constrained")
    for h,p in allp.items():
        ax.plot(p.az_deg,p.horizon_deg,label=f"{h} m",lw=1)
        u=p[~p.coverage_complete]
        if len(u): ax.scatter(u.az_deg,u.horizon_deg,s=6,marker="x",label=f"Incomplete {h} m")
    ax.set(xlim=(0,360),xlabel="Azimuth (° clockwise from true north)",ylabel="Terrain horizon elevation (°)")
    ax.set_xticks(np.arange(0,361,45));ax.grid(alpha=.2);ax.legend()
    ax.set_title(f"{site} • NASA LOLA sampled horizon")
    fig.savefig(root/"figures"/f"{site}_horizon.png",dpi=140);plt.close(fig)

def validate_config(s,g):
    a,b,end=[pd.Timestamp(s[k]) for k in ("A_utc","B_utc","end_utc")]
    if any(str(t.tz)!="UTC" for t in (a,b,end)) or a!=a.floor("15min") or b-a!=pd.Timedelta(days=14) or end-b!=pd.Timedelta(hours=72):
        raise ValueError("UNSUPPORTED_CONFIG: scenario boundaries")
    if (s["D_hours"],s["model_step_minutes"],s["start_step_minutes"],g["panel_height_m"],g["antenna_height_m"])!=(72,5,15,1,2):
        raise ValueError("UNSUPPORTED_CONFIG: mission dimensions")
    if g["R_ref_m"]!=R or g["version"]!=s["geometry_version"] or s["site_ids"]!=["Site01_P1","Site04_P1"]:
        raise ValueError("UNSUPPORTED_CONFIG: geometry or sites")
    return a,b,end

def stage_dem(root,nasa_dir,key,records,site_key=None):
    rec=records[key]
    if rec["status"] not in {"VERIFIED_BYTES","PASS"}: raise FileNotFoundError(rec.get("reason",key))
    path=nasa_dir/rec["filename"]
    with DEM(path,key) as d:
        if key=="dem80" and not np.allclose(d.ds.res,80) or key=="dem240" and not np.allclose(d.ds.res,240) or site_key and not np.allclose(d.ds.res,5):
            raise ValueError(f"Unexpected pixel size {d.ds.res}")
        m=d.meta()
        if m["pixel_registration"] not in {"Area","Point"}: raise ValueError("Pixel registration absent")
        if key.endswith("_dem") or key in {"dem80","dem240"}:
            m["vertical_reference"]="LOLA radial height above 1737400 m sphere (source lineage); MOON_ME/DE421"
        m["unit_from_source"]=rec["unit"]
        q=raster_stats(d)
        if key.endswith("_count") and q["min"]<0: raise ValueError("Negative LOLA count")
        if key.endswith("_error") and q["min"]<0: raise ValueError("Negative uncertainty")
        site=roi=None
        if site_key and key.endswith("_dem"):
            rr=records[site_key+"_roi"]
            if rr["status"] not in {"PASS","VERIFIED_BYTES"}: raise FileNotFoundError(rr.get("reason",rr["filename"]))
            site,roi=choose_site(d,nasa_dir/rr["filename"],site_key,rec["sha256"])
            records[site_key+"_roi"]["status"]="PASS"
            records[site_key+"_roi"]["metadata"]={"validated_site_roi_id":site["roi_id"],"crs_wkt":site["roi_crs_wkt"]}
        raster_figure(root,d,rec["unit"],site,roi)
    rec.update(status="PASS",metadata=m,stats=q)
    return site

def process_site(root,nasa_dir,site_key,scen,g,records,state,sites,eph,a,b,end,offline):
    keys={site_key+"_"+x for x in ("dem","count","error","roi")}
    for key in sorted(keys- {site_key+"_roi"}):
        site=stage_dem(root,nasa_dir,key,records,site_key)
        if site:
            sites.append(site);site_geojson(root/"processed/site_catalog.geojson",sites)
            stage(state,site_key+"_site_catalog","PASS",site_id=site["site_id"],roi=site["roi_id"])
    site=next(x for x in sites if x["site_id"]==site_key+"_P1")
    for layer in ("count","error"):
        ref=records[site_key+"_dem"]["metadata"]; comp=records[site_key+"_"+layer]["metadata"]
        if any(comp[k]!=ref[k] for k in ("shape","affine","crs_wkt")):
            raise ValueError("Ancillary layer grid differs from site DEM")
        rec=records[site_key+"_"+layer]
        with DEM(nasa_dir/rec["filename"],rec["id"]) as d:
            value=float(d.xy_at(site["x_m"],site["y_m"]))
            site[{"count":"lola_spots_at_site","error":"elevation_rms_error_m_at_site"}[layer]]=value if np.isfinite(value) else None
    site_geojson(root/"processed/site_catalog.geojson",sites)
    stage(state,site_key+"_dem_eda","PASS")
    heights={10:g["panel_height_m"],399:g["antenna_height_m"]}
    def pair(start,stop,step):
        outputs=[]
        for target,h in heights.items():
            df,m=fetch(root,site,target,h,start,stop,step,g["R_ref_m"],g["horizons_candidate_radius_m"],offline)
            eph.append(m); outputs.append(df)
        if not outputs[0].index.equals(outputs[1].index): raise ValueError("Sun/Earth timestamps differ")
        if any(x["missing_timestamps"] or x["missing_angles"] for x in eph[-2:]):
            raise ValueError("JPL coverage incomplete; inspect raw evidence")
        return outputs
    s,e=pair(a,end,5)
    stage(state,site_key+"_ephemeris","PASS",rows_per_target=len(s),boundary_utc=str(s.index[-1]))
    plot_ephem(root,site["site_id"],s,e)
    hdir=Path("processed/horizon")
    all_profiles={}
    with ExitStack() as stack:
        dems={}
        for label,key in [("5m",site_key+"_dem"),("80m","dem80"),("240m","dem240")]:
            rec=records[key]
            if rec["status"]!="PASS": raise FileNotFoundError(f"{key} not validated")
            dems[label]=stack.enter_context(DEM(nasa_dir/rec["filename"],key))
        x,y=site["x_m"],site["y_m"]; bb=dems["5m"].ds.bounds
        edge=min(x-bb.left,bb.right-x,y-bb.bottom,bb.top-y)
        near=min(8000,500*int((edge-500)//500))
        if near<1000: raise ValueError("Insufficient distance to 5 m footprint boundary")
        spec=list(zip(dems,[near,g["middle_radius_m"],g["scan_radius_m"]],g["radial_spacing_m"]))
        seams=[]; margin=None
        def qualifies(row):
            return (row["paired"]>=.9*row["sampled"] and abs(row["median_signed_m"])<=g["seam_median_limit_m"]
                and row["p95_abs_angle_deg"]<=g["seam_p95_angle_limit_deg"])
        for i,(seam,df) in enumerate(seam_diagnostics(site,dems,spec),1):
            seams.append(seam);csvout(root,f"reports/{site_key}_seam_fixed_{i}.csv",df)
        accepted=list(seams)
        if not qualifies(seams[0]) and qualifies(seams[1]):
            margin=g["footprint_margin_m"]
            accepted=[seams[1]]
            for phase in (0.,.25):
                row,df=next(seam_diagnostics(site,dems,spec,margin,phase))
                seams.append(row); accepted.append(row)
                csvout(root,f"reports/{site_key}_seam_footprint_phase{phase:g}.csv",df)
        for row in seams:
            row["accepted_for_model"]=any(row is x for x in accepted) and qualifies(row)
        csvout(root,f"reports/{site_key}_seam_summary.csv",pd.DataFrame(seams))
        for seam in accepted:
            if not qualifies(seam):
                raise ValueError(f"Seam failed provisional acceptance: {seam}")
        # 0.25° directions are the even-index exact subset of the 0.125° grid.
        for height in heights.values():
            fine=profile(site,dems,height,.125,spec,g["scan_radius_m"],margin)
            base=fine.iloc[::2].reset_index(drop=True).assign(az_step_deg=.25)
            if not base.coverage_complete.any(): raise ValueError("No fully covered azimuth")
            reference=reference_check(fine,site)
            for p in [base,fine]:
                csvout(root,hdir/f"{site_key}_h{height}_az{p.az_step_deg.iloc[0]}_r{g['scan_radius_m']}.csv",p)
            short=None
            if site_key=="Site01":
                short=profile(site,dems,height,.25,spec,g["comparison_radius_m"],margin)
                csvout(root,hdir/f"{site_key}_h{height}_az0.25_r{g['comparison_radius_m']}.csv",short)
            all_profiles[height]=(base,fine,short,reference)
    near_used=all_profiles[1][0].near_switch_radius_m
    stage(state,site_key+"_geometry","PASS",scan_radii_m=[g["middle_radius_m"],g["scan_radius_m"]],
          near_strategy="footprint" if margin is not None else "fixed",
          near_switch_radius_min_m=float(near_used.min()),near_switch_radius_max_m=float(near_used.max()),
          fixed_seam_p95_angle_deg=seams[0]["p95_abs_angle_deg"],
          selected_seam_checks=accepted,
          checks={str(h):ps[3] for h,ps in all_profiles.items()},
          covered_pct={str(h):float(100*ps[0].coverage_complete.mean()) for h,ps in all_profiles.items()})
    plot_horizon(root,site["site_id"],{h:ps[0] for h,ps in all_profiles.items()})
    def v(p,st=s,et=e): return visibility(st,et,all_profiles[1][p],all_profiles[2][p])
    bvis=v(0);bvis["site_id"]=site["site_id"]; bvis["scenario_id"]=scen["scenario_id"]; bvis["scenario_status"]="PROVISIONAL"
    csvout(root,f"processed/visibility/{site_key}_intervals.csv",bvis)
    constraints=scen["example_constraints"]; d,e_max=constraints["max_darkness_hours"],constraints["max_earth_blackout_hours"]
    wins=grid_windows(bvis,a,b,d,e_max)
    wins.insert(0,"site_id",site["site_id"]); wins.insert(1,"scenario_status","PROVISIONAL")
    csvout(root,f"processed/visibility/{site_key}_windows.csv",wins)
    stage(state,site_key+"_visibility","PASS","Executed under the provisional scenario; sampled model only",start_count=len(wins),
          states={x:bvis[x].value_counts().to_dict() for x in ("sun_state","earth_state","joint_state")})
    if site_key=="Site01":
        cols=["sun_state","earth_state","joint_state"]
        finer=v(1);shorter=v(2)
        sens={"scenario_status":"PROVISIONAL","site_id":site["site_id"],"geometry_tolerance_status":g["tol_status"]}
        for name,q,pidx in [("azimuth_0.25_vs_0.125",finer,1),("radius_400km_vs_300km",shorter,2)]:
            angular={}
            for h,ps in all_profiles.items():
                target=ps[pidx]; basez,_=lookup(ps[0],target.az_deg)
                dif=abs(basez-target.horizon_deg.to_numpy()); dif=dif[np.isfinite(dif)]
                angular[str(h)]=dict(comparable=int(len(dif)),p95_abs_deg=float(np.percentile(dif,95)) if len(dif) else None,
                    max_abs_deg=float(dif.max()) if len(dif) else None)
            vw=grid_windows(q,a,b,d,e_max)
            changed=int((vw.decision!=wins.decision).sum())
            dur={col:float((vw[col]-wins[col]).abs().max()*60) for col in wins if col.endswith(("_L","_U"))}
            tim=sensitivity(bvis,q,cols)
            sens[name]=dict(angles_by_height_m=angular,temporal=tim,decisions_changed=changed,
                 max_duration_delta_minutes=dur,sensitive=bool(changed or any((x["max_abs_deg"] or 0)>g["tol_horizon_deg"] for x in angular.values()) or max(dur.values())>g["tol_duration_minutes"] or any((x["max_matched_event_shift_minutes"] or 0)>g["tol_event_minutes"] or x["events_first"]!=x["events_second"] for x in tim.values())))
        case_end=a+pd.Timedelta(hours=72)
        s1,e1=pair(a,case_end,1)
        v1=v(0,s1,e1); v5=bvis[bvis.end_utc<=case_end]
        b5,c5,d5=analyze(v5,a,d,e_max);b1,c1,d1=analyze(v1,a,d,e_max)
        td={k:[float(abs(x-y)*60) for x,y in zip(b5[k],b1[k])] for k in b5}
        ts=sensitivity(v5,v1,cols)
        sens["time_5min_vs_1min"]={"case_start":str(a),"case_end":str(case_end),"window":"first supported 72h activity; both targets",
            "temporal":ts,"decision_5min":d5,"decision_1min":d1,"bounds_abs_delta_minutes":td,
            "sensitive":bool(d5!=d1 or max(max(x) for x in td.values())>g["tol_duration_minutes"] or any((x["max_matched_event_shift_minutes"] or 0)>g["tol_event_minutes"] or x["events_first"]!=x["events_second"] for x in ts.values()))}
        dump(root/"reports/sensitivity.json",sens)
        stage(state,"Site01_sensitivity","PASS","Measured both angular steps, both time steps and both radii; tolerance values provisional")

def reports(root,state,records,sites,eph):
    def write(name,lines): (root/"reports"/name).write_text("\n".join(lines)+"\n",encoding="utf-8")
    dem_rows=[f"| {r['id']} | {r['metadata']['shape']} | {r['metadata']['pixel_size_m']} | {r['stats']['min']:.3f} | {r['stats']['max']:.3f} | {r['stats']['nodata_percent']:.3f} |" for r in records.values() if "stats" in r]
    eph_rows=[f"| {r['name']} | {r['received_rows']}/{r['expected_rows']} | {r['missing_timestamps']} | {r['missing_angles']} | {r['elevation_min_deg']:.4f} to {r['elevation_max_deg']:.4f} |" for r in eph if r['elevation_min_deg'] is not None]
    write("eda_summary.md",["# HOSA data EDA","","NASA PGDA LOLA (MOON_ME/DE421); JPL Horizons, PROVISIONAL scenario.","",
         "| Raster | Shape | Pixel spacing (m) | Min (source unit) | Max (source unit) | NoData % |","|---|---|---|---:|---:|---:|",*dem_rows,"",
         "| Horizons query | Received / expected | Missing UTC | Missing angles | Elevation (°) |","|---|---:|---:|---:|---|",*eph_rows,"",
         "Exact windowed counts, moments and min/max, with systematic-sample percentiles in the manifest. Preview figures are downsampled by nearest neighbour; sparse NoData can be absent from previews. A 5 m spacing is not effective resolution. The count layer records LOLA shots, including zero at interpolated cells."])
    write("data_quality.md",["# Provenance and data quality","",
         "- NASA [PGDA 78](https://pgda.gsfc.nasa.gov/products/78) and [PGDA 90](https://pgda.gsfc.nasa.gov/products/90); [Horizons](https://ssd-api.jpl.nasa.gov/doc/horizons.html).",
         "- Full original raster SHA-256 is in source_manifest.json, with raw HTTP provenance. No raw DEM is repackaged. Count and RMS uncertainty use their own source units.",
         "- Raster CRS is checked against a Moon sphere of 1,737,400 m and independent south polar stereographic equations at two reference points. No Earth CRS substitution.",
         "- WKT describes projection geometry; vertical datum follows the LOLA radial height source lineage, not merely the projected CRS. The Horizons response independently reports three matching reference radii, east-positive longitude and high-precision Mean Earth. Apparent Sun/Earth centre angles are airless.",
         "- Native registered pixel centres are recovered from the corner affine once. Nearest pixel terrain sampling; explicit 5/80/240 m seam comparisons, no fitted vertical bias. A fixed near seam that fails the same tolerance is replaced only when a footprint-following seam (275 m inset) passes at two angular phases.",
         "- GeoJSON-shaped site catalog carries a lunar coordinate declaration; do not load as terrestrial WGS84.",
         "- DEM error is RMS, not a bound or a propagated probability. The finite-radius model, smoothing, subpixel relief and temporal sampling limit interpretation.",
         "",*[f"- {x['site_id']}: longitude {x['lon_e_deg']:.8f}°E, latitude {x['lat_deg']:.8f}°, height {x['dem_z_m']:.3f} m; ROI {x['roi_id']}." for x in sites]])
    write("scientific_validation.md",["# Scientific validation","",
         "Run status concerns the data pipeline. All scenario-dependent results are provisional. Visibility is geometric for the sampled Sun/Earth centres.",
         "", "| Check | Status | Detail |","|---|---|---|",
         *[f"| {k} | {v['status']} | {str(v.get('detail','')).replace('|','/').replace(chr(10),' ')[:360]} |" for k,v in state.items()],
         "", "See pytest.log for synthetic cases, source_manifest.json for provenance, seam reports and sensitivity.json for actual measured convergence. Reference check recomputes sampled real blockers via Cartesian-to-ENU geometry; it is not an independent Moon Trek/CMS comparison. G0 thresholds and scenario epoch await review."])
    inventory(root,list(records.values()),eph)

def run(root, *, repository_root, nasa_dir, offline=False, site01_only=False):
    root=Path(root).resolve()
    for p in ("reports","manifests","figures","processed"): (root/p).mkdir(parents=True,exist_ok=True)
    state={}; started=utc_now(); records={x["id"]:dict(x,status="NOT_REQUESTED") for x in sources()}; sites=[]; eph=[]
    previous=root/"reports/execution_status.json"
    if previous.exists():
        old=load(previous)
        history=root/"reports/history"/old["started_utc"].replace(":","-")
        history.mkdir(parents=True,exist_ok=True)
        for p in (previous,root/"reports/errors.log"):
            if p.is_file(): shutil.copy2(p,history/p.name)
        (root/"reports/errors.log").unlink(missing_ok=True)
    env=environment(root)
    scen=load(root/"config/scenario.json"); g=load(root/"config/geometry_config.json")
    a,b,end=validate_config(scen,g)
    env["network_mode"]="cache only" if offline else "official NASA/JPL HTTPS enabled"
    dump(root/"reports/environment_check.json",env)
    ep=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    out=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","--basetemp",str(root/".test-tmp"),"tests/test_science.py"],
                       cwd=repository_root,env=ep,capture_output=True,text=True,encoding="utf-8",errors="replace")
    (root/"reports/pytest.log").write_text(out.stdout+out.stderr,encoding="utf-8")
    stage(state,"synthetic_tests","PASS" if out.returncode==0 else "FAIL",out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-400:])
    items=sources()
    for site in REGIONS:
        if site=="Site04" and (site01_only or state.get("Site01_pipeline",{}).get("status")!="PASS" or state["synthetic_tests"]["status"]!="PASS"):
            stage(state,"Site04_pipeline","BLOCKED","Site04 awaits successful Site01 gate or was excluded by --site01-only");continue
        ids={i["id"] for i in items if i["site"]==site}
        if site=="Site01": ids|={"p78_readme","dem80","dem240"}
        records.update(select_sources(nasa_dir,items,ids,offline))
        for i in sorted(ids):
            r=records[i]
            stage(state,"source_"+i,"PASS" if r["status"]=="VERIFIED_BYTES" else r["status"],r.get("reason"),bytes=r.get("bytes"),sha256=r.get("sha256"))
        try:
            if site=="Site01":
                for key in ("dem80","dem240"):
                    try:
                        stage_dem(root,nasa_dir,key,records)
                        stage(state,key+"_eda","PASS")
                    except Exception as e:
                        stage(state,key+"_eda","BLOCKED" if isinstance(e,FileNotFoundError) else "FAIL",str(e))
            if state["synthetic_tests"]["status"]!="PASS": raise ValueError("Synthetic tests failed; inspect pytest.log")
            process_site(root,nasa_dir,site,scen,g,records,state,sites,eph,a,b,end,offline)
            stage(state,site+"_pipeline","PASS")
        except Exception as e:
            with (root/"reports/errors.log").open("a",encoding="utf-8") as f: f.write(site+"\n"+traceback.format_exc()+"\n")
            stage(state,site+"_pipeline","BLOCKED" if isinstance(e,(OSError,FileNotFoundError)) else "FAIL",f"{type(e).__name__}: {e}")
    verdict="PASS" if all(state.get(s+"_pipeline",{}).get("status")=="PASS" for s in REGIONS) else "PARTIAL"
    status=dict(pipeline_status=verdict,provider=env["provider"],started_utc=started,finished_utc=utc_now(),method_version=VERSION,
         scenario_status="PROVISIONAL",scenario_utc=scen["A_utc"],steps=state,
         note="Kaggle version status is external to Python and must be verified in the UI or CLI.")
    dump(root/"reports/execution_status.json",status)
    reports(root,state,records,sites,eph)
    print("PIPELINE RESULT",verdict,flush=True)
    return status
