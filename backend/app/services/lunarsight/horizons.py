import csv, hashlib, io, json, math, re, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .acquire import JPL, JPL_DOC, dump, load, hashfile, utc_now

MANUAL="https://ssd.jpl.nasa.gov/horizons/manual.html"
MONTHS="Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
LIMIT=8_000_000
ADAPTER_VERSION="0.1.0"

def expected_grid(start,stop,minutes):
    start,stop=pd.Timestamp(start),pd.Timestamp(stop)
    delta=pd.Timedelta(minutes=minutes)
    if start.tzinfo is None or stop.tzinfo is None or minutes not in (1,5) or stop<=start or (stop-start)%delta:
        raise ValueError("Expected an aligned aware UTC query interval")
    return pd.date_range(start.tz_convert("UTC"),stop.tz_convert("UTC"),freq=delta)

def request_params(target,lon,lat,z,device_h,r_dem,r_jpl,start,stop,minutes):
    expected_grid(start,stop,minutes)
    if target not in (10,399) or not all(math.isfinite(x) for x in (lon,lat,z,device_h,r_dem,r_jpl)) or not -90<lat<90 or r_dem<=0 or r_jpl<=0:
        raise ValueError("Invalid lunar observer configuration")
    altitude_km=(r_dem+z+device_h-r_jpl)/1000
    stamp=lambda t: pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S")
    kwargs=dict(COMMAND=str(target),OBJ_DATA="NO",MAKE_EPHEM="YES",EPHEM_TYPE="OBSERVER",
        CENTER="coord@301",COORD_TYPE="GEODETIC",SITE_COORD=f"{lon%360:.9f},{lat:.9f},{altitude_km:.9f}",
        START_TIME=stamp(start),STOP_TIME=stamp(stop),STEP_SIZE=f"{minutes} min",QUANTITIES="4",
        TIME_TYPE="UT",TIME_DIGITS="SECONDS",CSV_FORMAT="YES",APPARENT="AIRLESS",
        ANG_FORMAT="DEG",SKIP_DAYLT="NO",EXTRA_PREC="YES",CAL_FORMAT="CAL")
    return dict(format="json",**{k:f"'{v}'" for k,v in kwargs.items()})

def header_value(header,label):
    m=re.search(rf"^\s*{re.escape(label)}\s*:\s*(.+)$",header,re.M)
    if not m: raise ValueError(f"Missing Horizons header {label}")
    return m.group(1).strip()

def timestamp(field):
    m=re.fullmatch(r"(?:A\.D\.\s+)?(\d{4})-([A-Za-z]{3})-(\d\d) (\d\d):(\d\d):(\d\d)(?:\.0+)?",field.strip())
    if not m: raise ValueError(f"Unexpected JPL timestamp: {field!r}")
    y,mo,d,hh,mm,ss=m.groups()
    return datetime(int(y),MONTHS.index(mo.title())+1,int(d),int(hh),int(mm),int(ss),tzinfo=timezone.utc)

def parse(payload,params,start,stop,step,r_jpl):
    if payload.get("error"): raise ValueError("Horizons API: "+str(payload["error"])[:500])
    signature=payload.get("signature",{})
    if not str(signature.get("version","")).startswith("1."): raise ValueError(f"Unrecognized Horizons schema: {signature}")
    result=payload.get("result","")
    if result.count("$$SOE")!=1 or result.count("$$EOE")!=1: raise ValueError("Missing Horizons output table: "+result[-420:])
    header, data = result.split("$$SOE",1)
    data,notes=data.split("$$EOE",1)
    target=int(params["COMMAND"].strip("'"))
    if f"({'10' if target==10 else '399'})" not in header_value(header,"Target body name"):
        raise ValueError("Target body header mismatch")
    if "(301)" not in header_value(header,"Center body name"): raise ValueError("Observer is not Moon")
    frame=header_value(header,"Center pole/equ")
    if not (("MEAN_ME" in frame or "MOON_ME" in frame) and "East-longitude positive" in frame and "IAU_MOON" not in frame):
        raise ValueError(f"Unsupported lunar frame {frame}")
    center=header_value(header,"Center geodetic")
    if not all(x in center for x in ("E-lon(deg)","Lat(deg)","Alt(km)")): raise ValueError("Observer units absent")
    lon,lat,alt=map(float,center.split("{")[0].strip().split(","))
    a,b,c=map(float,params["SITE_COORD"].strip("'").split(","))
    if abs((lon-a+180)%360-180)>6e-6 or abs(lat-b)>6e-6 or abs(alt-c)>5.1e-6:
        raise ValueError(f"Observer echo mismatch: {center} vs {params['SITE_COORD']}")
    radii_str=header_value(header,"Center radii")
    if " km" not in radii_str: raise ValueError("Missing lunar radii unit")
    radii=[float(x)*1000 for x in radii_str.split("km")[0].split(",")]
    if len(radii)!=3 or not all(abs(r-r_jpl)<1e-5 for r in radii):
        raise ValueError(f"Unexpected lunar reference shape {radii}")
    if "AIRLESS" not in header_value(header,"Atmos refraction"): raise ValueError("Expected airless")
    if not all(" UT" in header_value(header,key) for key in ("Start time","Stop  time")): raise ValueError("Non-UT time")
    if not re.search(rf"^\s*{step}\s+minute",header_value(header,"Step-size"),re.I):
        raise ValueError("Step header mismatch")
    line=next((x for x in header.splitlines() if "Date__(UT)" in x and "Azimuth_(a-app)" in x),None)
    if not line or "Units: DEGREES" not in notes: raise ValueError("Missing UT/airless angle columns or degrees")
    if "times after 1962 are in utc" not in " ".join(notes.lower().split()): raise ValueError("Missing UT-to-UTC convention")
    names=[v.strip() for v in next(csv.reader([line]))]
    iaz=names.index("Azimuth_(a-app)"); iel=names.index("Elevation_(a-app)")
    rows=[]
    def angle(s):
        s=s.strip()
        if s.lower() in {"","n.a.","na","n/a"}: return float("nan")
        x=float(s)
        if not math.isfinite(x): raise ValueError("Nonfinite Horizons angle")
        return x
    for row in csv.reader(io.StringIO(data)):
        if not row or not any(x.strip() for x in row): continue
        if len(row)!=len(names): raise ValueError(f"Unexpected Horizons CSV arity {len(row)}")
        t=timestamp(row[0]); az=angle(row[iaz]); el=angle(row[iel])
        if (np.isfinite(az) and not 0<=az<=360) or (np.isfinite(el) and not -90<=el<=90): raise ValueError("Horizons angle out of range")
        rows.append((t, az%360, el))
    df=pd.DataFrame(rows,columns=["utc","az_deg","el_deg"]).set_index("utc")
    grid=expected_grid(start,stop,step)
    if not len(df) or df.index.has_duplicates or not df.index.is_monotonic_increasing or not df.index.isin(grid).all():
        raise ValueError("Missing table, duplicate, unordered or off-grid UTC")
    missing=int((~grid.isin(df.index)).sum())
    if grid[0] not in df.index or grid[-1] not in df.index: raise ValueError("Response lacks scenario boundary timestamp")
    df["row_present"]=True
    df=df.reindex(grid)
    df["row_present"]=df["row_present"].eq(True)
    df.index.name="utc"
    meta=dict(signature=signature,target=target,observer_lon_e_deg=lon,observer_lat_deg=lat,observer_alt_km=alt,
        observer_frame=frame,observer_radii_m=radii,angle_units="degree",time_scale="UTC",step_minutes=step,
        expected_rows=len(grid),received_rows=len(rows),missing_timestamps=missing,
        missing_angles=int(df[["az_deg","el_deg"]].isna().any(axis=1).sum()),
        azimuth_min_deg=None if df.az_deg.isna().all() else float(df.az_deg.min()),
        azimuth_max_deg=None if df.az_deg.isna().all() else float(df.az_deg.max()),
        elevation_min_deg=None if df.el_deg.isna().all() else float(df.el_deg.min()),
        elevation_max_deg=None if df.el_deg.isna().all() else float(df.el_deg.max()))
    return df,meta,header

def fetch(root,site,target,h,start,stop,step,r_dem,r_jpl,offline=False):
    import requests
    root=Path(root)
    params=request_params(target,site["lon_e_deg"],site["lat_deg"],site["dem_z_m"],h,r_dem,r_jpl,start,stop,step)
    identity=dict(method_version=ADAPTER_VERSION,site_id=site["site_id"],dataset_sha256=site["dem_sha256"],observer_height_m=h,endpoint=JPL,params=params)
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    name=f"{site['site_id']}_{'sun' if target==10 else 'earth'}_{step}min_{key[:12]}"
    raw=root/"raw/horizons"/f"{name}.json"
    receipt=raw.with_suffix(".receipt.json")
    raw.parent.mkdir(parents=True,exist_ok=True)
    if raw.exists():
        record=load(receipt)
        if record["identity"]!=identity or record["sha256"]!=hashfile(raw):
            raise ValueError(f"Horizons cache integrity failure: {name}")
    else:
        if offline: raise FileNotFoundError(f"Offline and no exact Horizons cache: {name}")
        for attempt in range(3):
            try:
                r=requests.get(JPL,params=params,timeout=(15,75),stream=True)
                with r:
                    r.raise_for_status()
                    if r.url.split("/")[2]!="ssd.jpl.nasa.gov" or not r.url.startswith("https://"): raise ValueError("Unexpected JPL redirect")
                    body=bytearray()
                    for chunk in r.iter_content(262144):
                        body.extend(chunk)
                        if len(body)>LIMIT: raise ValueError("Horizons response exceeds byte cap")
                    rec_headers={k:r.headers.get(k) for k in ("Date","Content-Type","Content-Length","ETag")}
                break
            except (requests.ConnectionError,requests.Timeout,requests.HTTPError) as e:
                if attempt==2 or (isinstance(e,requests.HTTPError) and e.response.status_code not in (429,500,502,503,504)): raise
                time.sleep(1.5*(attempt+1))
        tmp=raw.with_suffix(".part")
        tmp.write_bytes(body); tmp.replace(raw)
        record=dict(name=name,identity=identity,url=r.url,accessed_utc=utc_now(),raw_file=raw.relative_to(root).as_posix(),
            sha256=hashfile(raw),bytes=len(body),http_headers=rec_headers)
        dump(receipt,record)
    df,meta,header=parse(load(raw),params,start,stop,step,r_jpl)
    path=root/"processed/ephemeris"/f"{name}.csv"
    path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(path,date_format="%Y-%m-%dT%H:%M:%SZ")
    header_path=raw.with_suffix(".header.txt")
    header_path.write_text(header,encoding="utf-8")
    return df,dict(record,**meta,parsed_file=path.relative_to(root).as_posix(),header_file=header_path.relative_to(root).as_posix())
