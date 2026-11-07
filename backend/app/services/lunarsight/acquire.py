import csv, hashlib, json, os, shutil, tarfile, platform, re, time
from pathlib import Path
from datetime import datetime, timezone

P78 = "https://pgda.gsfc.nasa.gov/products/78"
P90 = "https://pgda.gsfc.nasa.gov/products/90"
PGDA = "https://pgda.gsfc.nasa.gov/data"
JPL = "https://ssd.jpl.nasa.gov/api/horizons.api"
JPL_DOC = "https://ssd-api.jpl.nasa.gov/doc/horizons.html"
VERSION = "0.2.0"
TIFF_MAGIC = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
REGIONS = {"Site01":"Connecting Ridge","Site04":"Shackleton Rim"}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def sources():
    out = [dict(id="p78_readme", filename="PGDA78_README", url=f"{PGDA}/LOLA_5mpp/README", source_page=P78, role="metadata", unit=None, site=None)]
    for site in REGIONS:
        for role, suffix, unit in [("dem","surf.tif","m"),("error","toterr.tif","m RMS"),("count","ldec.tif","LOLA spots"),("roi","ROIs.tgz",None)]:
            name = f"{site}_{'final_adj_5mpp_' if role != 'roi' else ''}{suffix}"
            out.append(dict(id=f"{site}_{role}",filename=name,url=f"{PGDA}/LOLA_5mpp/{site}/{name}",source_page=P78,role=role,unit=unit,site=site,frame="MOON_ME/DE421"))
    for key, stem, size in [("dem80","80S_80MPP",181),("dem240","60S_240MPP",210)]:
        name=f"LDEM_{stem}_ADJ.TIF"
        out.append(dict(id=key, filename=name, url=f"{PGDA}/LOLA_20mpp/{name}", source_page=P90,role="dem",unit="m",site=None, frame="MOON_ME/DE421", nasa_display_size=f"{size}M"))
    return out

def hashfile(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def dump(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,default=str)+"\n",encoding="utf-8")
    tmp.replace(path)

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_payload(path,role):
    with path.open("rb") as f: magic=f.read(4)
    if role in {"dem","error","count"} and magic not in TIFF_MAGIC:
        raise ValueError("Unexpected TIFF signature")
    if role=="roi":
        if magic[:2]!=b"\x1f\x8b": raise ValueError("Unexpected gzip signature")
        with tarfile.open(path,"r:gz") as t:
            if not any(x.name.lower().endswith(".shp") for x in t):
                raise ValueError("ROI archive has no shapefile")
    if role=="metadata":
        body=path.read_text(encoding="utf-8",errors="replace")
        if len(body)<100 or "<html" in body[:300].lower(): raise ValueError("Unexpected NASA README payload")

def ranged_download(session,url,partial,limit):
    """Validate ordered byte ranges and the asset identity before joining them."""
    import requests
    offset=0; total=None; signature=None; sha=hashlib.sha256(); slice_size=12*1024*1024
    with partial.open("wb") as f:
        while total is None or offset<total:
            last=offset+slice_size-1 if total is None else min(total-1,offset+slice_size-1)
            for attempt in range(3):
                try:
                    with session.get(url,timeout=(15,90),stream=True,headers={"Accept-Encoding":"identity","Range":f"bytes={offset}-{last}"}) as r:
                        r.raise_for_status()
                        if r.status_code!=206 or r.url!=url:
                            raise ValueError("Expected an HTTP 206 response from the original NASA asset")
                        m=re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",r.headers.get("Content-Range",""))
                        if not m: raise ValueError("Missing Content-Range")
                        first,stop,count=map(int,m.groups())
                        if not 0<count<=limit or first!=offset or stop!=min(last,count-1):
                            raise ValueError(f"Unexpected byte range {m.group(0)}")
                        identity=(r.headers.get("ETag"),r.headers.get("Last-Modified"),count)
                        if signature is not None and signature!=identity:
                            raise ValueError("NASA asset identity changed during transfer")
                        if not any(identity[:2]): raise ValueError("NASA asset identity headers absent")
                        body=r.content
                        if len(body)!=stop-first+1: raise ValueError("Truncated NASA range")
                        headers={k:r.headers.get(k) for k in ("ETag","Last-Modified","Content-Type","Accept-Ranges")}
                    break
                except (requests.ConnectionError,requests.Timeout,requests.exceptions.ChunkedEncodingError):
                    if attempt==2: raise
                    time.sleep(attempt+1)
            signature=identity;total=count;f.write(body);sha.update(body);offset=stop+1
    return dict(final_url=url,bytes=total,sha256=sha.hexdigest(),accessed_utc=utc_now(),status="VERIFIED_BYTES",
                transfer="ordered validated HTTP byte ranges",http_headers=dict(headers,**{"Content-Length":str(total)}))

def download(nasa_dir,item,offline=False):
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    path=Path(nasa_dir)/item["filename"]
    receipt=path.with_name(path.name+".receipt.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        validate_payload(path,item["role"])
        if not receipt.exists(): raise ValueError(f"Unprovenanced raw file: {path.name}")
        rec=load(receipt)
        if rec["url"]!=item["url"] or rec["sha256"]!=hashfile(path) or rec["bytes"]!=path.stat().st_size:
            raise ValueError(f"Raw cache integrity failure: {path.name}")
        return rec
    if offline: raise FileNotFoundError(path.name)
    limit=450_000_000 if item["role"] in {"dem","error","count"} else 10_000_000
    if shutil.disk_usage(path.parent).free < limit+100_000_000:
        raise OSError("Insufficient disk for bounded download")
    partial=path.with_suffix(path.suffix+".part")
    try:
        with requests.Session() as s:
            s.mount("https://",HTTPAdapter(max_retries=Retry(total=2,backoff_factor=.6,status_forcelist=(429,500,502,503,504),respect_retry_after_header=False)))
            if item["id"] in {"dem80","dem240"}:
                rec=dict(item,**ranged_download(s,item["url"],partial,limit))
                validate_payload(partial,item["role"])
                partial.replace(path)
                dump(receipt,rec)
                return rec
            with s.get(item["url"],timeout=(15,90),stream=True,headers={"Accept-Encoding":"identity"}) as r:
                r.raise_for_status()
                if r.url.split("/")[2]!="pgda.gsfc.nasa.gov" or not r.url.startswith("https://"):
                    raise ValueError("Unexpected source host")
                cl=r.headers.get("Content-Length")
                if cl and int(cl)>limit: raise ValueError("Source exceeds configured byte limit")
                total=0; sha=hashlib.sha256()
                with partial.open("wb") as f:
                    for chunk in r.iter_content(1024*1024):
                        total+=len(chunk)
                        if total>limit: raise ValueError("Source exceeds configured byte limit")
                        f.write(chunk);sha.update(chunk)
                if total==0 or (cl and int(cl)!=total): raise ValueError("Empty or truncated download")
                validate_payload(partial,item["role"])
                rec=dict(item,final_url=r.url,bytes=total,sha256=sha.hexdigest(),accessed_utc=utc_now(),status="VERIFIED_BYTES",http_headers={k:r.headers.get(k) for k in ("Content-Length","ETag","Last-Modified","Content-Type")})
        partial.replace(path)
        dump(receipt,rec)
        return rec
    finally:
        partial.unlink(missing_ok=True)

def inventory(root, records, ephemerides=()):
    root=Path(root)
    dump(root/"manifests/source_manifest.json",{"method_version":VERSION,"updated_utc":utc_now(),"records":records,"horizons":list(ephemerides)})
    keys=["id","site","role","filename","url","source_page","frame","unit","nasa_display_size","bytes","sha256","accessed_utc","status","reason"]
    with (root/"reports/data_inventory.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(records)

def environment(root):
    import importlib.metadata, sys
    root=Path(root); out={"utc":utc_now(),"python":sys.version,"platform":platform.platform(),
         "provider":"Kaggle" if Path("/kaggle/working").is_dir() else "Local Windows",
         "disk_free_bytes":shutil.disk_usage(root).free,"packages":{}}
    for pkg in ("numpy","pandas","rasterio","pyproj","geopandas","shapely","matplotlib","scipy","requests","pytest","nbformat","psutil"):
        try: out["packages"][pkg]=importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError: out["packages"][pkg]=None
    try:
        import psutil
        out["ram_total_bytes"]=psutil.virtual_memory().total
        out["ram_available_bytes"]=psutil.virtual_memory().available
    except ImportError: pass
    dump(root/"reports/environment_check.json",out)
    return out
