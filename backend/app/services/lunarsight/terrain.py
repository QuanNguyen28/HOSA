from collections import OrderedDict
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import math, re, tarfile, shutil
import numpy as np
import rasterio as rio
from rasterio.enums import Resampling
from rasterio.windows import Window
from pyproj import CRS, Transformer
from .acquire import REGIONS, dump

R=1737400.0

def lunar_crs(value):
    crs=CRS.from_user_input(value)
    if not crs.is_projected or not all(a.unit_conversion_factor==1 for a in crs.axis_info):
        raise ValueError("Expected a projected lunar CRS in metres")
    ell=crs.ellipsoid
    if not np.allclose([ell.semi_major_metre,ell.semi_minor_metre],R,rtol=0,atol=.01):
        raise ValueError(f"Unexpected lunar projection radius: {ell}")
    if "stereographic" not in crs.coordinate_operation.method_name.lower():
        raise ValueError("Expected polar stereographic")
    return crs

def independently_project(lon,lat):
    # PGDA polar stereographic, true scale at south pole, central meridian 0.
    lam,phi=np.deg2rad([lon,lat])
    rho=2*R*np.tan((np.pi/2+phi)/2)
    return rho*np.sin(lam),rho*np.cos(lam)

class DEM:
    def __init__(self,path,source_id):
        self.source_id=source_id; self.path=Path(path); self.ds=rio.open(path)
        self.crs=lunar_crs(self.ds.crs)
        self.fwd=Transformer.from_crs(self.crs.geodetic_crs,self.crs,always_xy=True)
        self.inv=Transformer.from_crs(self.crs,self.crs.geodetic_crs,always_xy=True)
        self.scale,self.offset=self.ds.scales[0],self.ds.offsets[0]
        if self.ds.count!=1 or not np.isfinite([self.scale,self.offset]).all() or self.scale==0:
            raise ValueError("Bad band configuration")
        refs=[]
        for lon,lat in [(0,-85),(90,-85)]:
            a=np.array(self.fwd.transform(lon,lat)); ref=np.array(independently_project(lon,lat))
            error=float(np.linalg.norm(a-ref))
            if error>.01: raise ValueError(f"Independent lunar projection mismatch: {a} vs {ref}")
            refs.append(dict(lon_deg=lon,lat_deg=lat,x_m=float(a[0]),y_m=float(a[1]),error_m=error))
        self.refs=refs; self.block_cache=OrderedDict()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def close(self): self.block_cache.clear(); self.ds.close()
    def array(self, **kw):
        a=self.ds.read(1,masked=True,**kw).astype("float64")
        x=a.filled(np.nan)*self.scale+self.offset
        x[~np.isfinite(x)]=np.nan
        return x
    def xy_at(self,x,y):
        """Nearest cell, using inverse corner affine and floor; outside/mask -> NaN."""
        x,y=np.broadcast_arrays(x,y)
        shape=x.shape; x,y=x.ravel(),y.ravel()
        finite=np.isfinite(x)&np.isfinite(y)
        cols,rows=(~self.ds.transform)*(np.where(finite,x,0.),np.where(finite,y,0.))
        rr,cc=np.floor(rows).astype("int64"),np.floor(cols).astype("int64")
        good=np.flatnonzero(finite&(rr>=0)&(rr<self.ds.height)&(cc>=0)&(cc<self.ds.width))
        out=np.full(x.shape,np.nan)
        block=256; stride=(self.ds.width+block-1)//block
        keys=(rr[good]//block)*stride+cc[good]//block
        order=np.argsort(keys,kind="stable")
        good=good[order]; keys=keys[order]
        limits=np.r_[0,np.flatnonzero(np.diff(keys))+1,len(keys)]
        for i,j in zip(limits[:-1],limits[1:]):
            if i==j: continue
            key=int(keys[i]); ro,co=(key//stride)*block,(key%stride)*block
            a=self.block_cache.get(key)
            if a is None:
                a=self.array(window=Window(co,ro,min(block,self.ds.width-co),min(block,self.ds.height-ro)))
                self.block_cache[key]=a
                if len(self.block_cache)>128: self.block_cache.popitem(last=False)
            else: self.block_cache.move_to_end(key)
            idx=good[i:j]; out[idx]=a[rr[idx]-ro,cc[idx]-co]
        return out.reshape(shape)
    def lonlat_at(self,lon,lat): return self.xy_at(*self.fwd.transform(lon,lat))
    def meta(self):
        d=self.ds
        nd=d.nodata
        return dict(shape=[d.height,d.width],pixel_size_m=list(d.res),affine=list(d.transform)[:6],
            bounds_xy_m=list(d.bounds),crs_wkt=self.crs.to_wkt(),dtype=d.dtypes[0],
            nodata=("NaN" if nd is not None and np.isnan(nd) else nd),scale=self.scale,offset=self.offset,
            pixel_registration=d.tags().get("AREA_OR_POINT","not tagged"), band_unit=d.units[0],tags=d.tags(),
            checks_against_spherical_projection=self.refs)

def raster_stats(dem):
    """Exact finite count and float64 moments; deterministic 2D subsample for percentiles."""
    ds=dem.ds; n=0; mean=0.; m2=0.; lo=float("inf"); hi=-lo; sampled=[]; zero=0
    stride=max(1,math.ceil(math.sqrt(ds.width*ds.height/350000)))
    for row in range(0,ds.height,512):
        for col in range(0,ds.width,512):
            a=dem.array(window=Window(col,row,min(512,ds.width-col),min(512,ds.height-row)))
            v=a[np.isfinite(a)]
            if len(v):
                mn=float(v.mean()); delta=mn-mean; n2=n+len(v)
                m2+=float(np.sum((v-mn)**2))+delta*delta*n*len(v)/n2
                mean+=delta*len(v)/n2; n=n2
                lo=min(lo,float(v.min())); hi=max(hi,float(v.max())); zero+=int(np.count_nonzero(v==0))
            sampled.append(a[(-row)%stride::stride,(-col)%stride::stride].ravel())
    vals=np.concatenate(sampled); vals=vals[np.isfinite(vals)]
    if not n or not len(vals): raise ValueError("No valid pixels for raster EDA")
    pct=[1,5,25,50,75,95,99]
    return dict(valid_pixels=n,nodata_pixels=ds.width*ds.height-n,
        nodata_percent=100*(1-n/(ds.width*ds.height)),zero_percent_of_valid=100*zero/n,
        min=lo,max=hi,mean=mean,std_population=math.sqrt(m2/n),
        percentiles=dict(zip(map(str,pct),map(float,np.percentile(vals,pct)))),
        percentile_method="systematic sample of pixel centres",percentile_stride_px=stride,percentile_n=len(vals))

def extract_roi(path,target):
    # Flatten only recognised shape components from an immutable NASA tarball.
    allowed={".shp",".shx",".dbf",".prj",".cpg"}; seen=set(); total=0
    with tarfile.open(path,"r:gz") as f:
        for m in f:
            name=PurePosixPath(m.name)
            if not m.isfile() or name.suffix.lower() not in allowed or name.name.startswith("._"): continue
            if name.is_absolute() or ".." in name.parts or "\\" in m.name or ":" in name.name:
                raise ValueError("Unsafe ROI archive member")
            if name.name.casefold() in seen: raise ValueError("Duplicate shapefile member")
            seen.add(name.name.casefold()); total+=m.size
            if total>40_000_000: raise ValueError("ROI extraction cap")
            with f.extractfile(m) as src,(target/name.name).open("xb") as dst: shutil.copyfileobj(src,dst)
    return sorted(target.glob("*.shp"))

def choose_site(dem,roi_archive,site,dem_sha):
    import geopandas as gpd
    from shapely.geometry import Point
    if site not in REGIONS: raise ValueError("Unknown site")
    with TemporaryDirectory(dir=Path(roi_archive).resolve().parents[2],prefix="roi_extract_") as tmp:
        paths=extract_roi(roi_archive,Path(tmp))
        if not paths: raise ValueError("Empty ROI archive")
        for path in paths:
            gdf=gpd.read_file(path)
            if gdf.crs is None: raise ValueError(f"No ROI CRS in {path.name}")
            if not lunar_crs(gdf.crs).equals(dem.crs,ignore_axis_order=True):
                gdf=gdf.to_crs(dem.crs)
            for idx,row in gdf.iterrows():
                g=row.geometry
                if g is None or not g.is_valid or g.is_empty or g.geom_type not in {"Polygon","MultiPolygon"}: continue
                p=g.representative_point(); rr,cc=dem.ds.index(p.x,p.y)
                for dr,dc in [(0,0)]+[(a,b) for a in range(-4,5) for b in range(-4,5) if a or b]:
                    r,c=rr+dr,cc+dc
                    if not (0<=r<dem.ds.height and 0<=c<dem.ds.width): continue
                    x,y=dem.ds.xy(r,c,offset="center")
                    z=float(dem.xy_at(x,y))
                    if not np.isfinite(z) or not g.contains(Point(x,y)): continue
                    lon,lat=dem.inv.transform(x,y); lon%=360
                    xx,yy=dem.fwd.transform(lon,lat)
                    affine_x,affine_y=dem.ds.transform*(c+.5,r+.5)
                    if math.hypot(xx-x,yy-y)>.001 or math.hypot(affine_x-x,affine_y-y)>.001 or dem.ds.index(xx,yy)!=(r,c):
                        raise ValueError("Site pixel-centre round trip failed")
                    props=dict(site_id=f"{site}_P1",region=REGIONS[site],lon_e_deg=lon,lat_deg=lat,dem_z_m=z,
                        roi_id=f"{path.stem}:{idx}",dataset_id=dem.source_id,dem_sha256=dem_sha,
                        coverage_status="VALID_ROI_PIXEL",pixel_row=r,pixel_col=c,x_m=x,y_m=y,
                        roi_crs_wkt=CRS.from_user_input(gdf.crs).to_wkt(),
                        selection="First valid snapped interior centre from lexically sorted NASA ROI shapefiles; demo point")
                    return props,g
    raise ValueError(f"No valid centre within NASA ROI for {site}")

def site_geojson(path,sites):
    # GeoJSON-shaped interchange with an explicit non-Earth spatial context.
    dump(path,dict(type="FeatureCollection",lunar_reference={"frame":"MOON_ME/DE421","radius_m":R,"axis_order":"east longitude [-180,180), latitude; degrees","rfc7946_earth_crs":False},
        features=[dict(type="Feature",id=s["site_id"],geometry=dict(type="Point",coordinates=[(s["lon_e_deg"]+180)%360-180,s["lat_deg"]]),properties=s) for s in sites]))

def raster_figure(root,dem,unit,site=None,roi=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ds=dem.ds; factor=max(1,math.ceil(max(ds.shape)/750))
    a=dem.array(out_shape=(max(1,ds.height//factor),max(1,ds.width//factor)),resampling=Resampling.nearest)
    extent=[ds.bounds.left/1000,ds.bounds.right/1000,ds.bounds.bottom/1000,ds.bounds.top/1000]
    vals=a[np.isfinite(a)]
    if not len(vals): return
    lo,hi=np.percentile(vals,[2,98]); fig,ax=plt.subplots(1,3,figsize=(14,4),layout="constrained")
    im=ax[0].imshow(a,extent=extent,cmap="terrain" if unit=="m" else "viridis",vmin=lo,vmax=max(hi,lo+1e-6))
    if site:
        x,y=site["x_m"]/1000,site["y_m"]/1000
        ax[0].plot(x,y,"r+",ms=9)
        if roi:
            for g in getattr(roi,"geoms",[roi]):
                rx,ry=g.exterior.xy; ax[0].plot(np.asarray(rx)/1000,np.asarray(ry)/1000,color="gold",lw=1)
        ax[0].set_title("Raster and chosen ROI pixel")
    else: ax[0].set_title("Raster preview")
    fig.colorbar(im,ax=ax[0],label=unit,shrink=.82)
    ax[1].hist(vals,bins=60,color="#3b7292");ax[1].set(title="Valid preview pixels",xlabel=unit,ylabel="Count")
    ax[2].imshow(~np.isfinite(a),extent=extent,cmap="gray_r",vmin=0,vmax=1);ax[2].set_title("NoData mask (black = missing)")
    for j in (0,2): ax[j].set(xlabel="X (km)",ylabel="Y (km)")
    fig.suptitle(f"NASA PGDA LOLA • {dem.source_id} • MOON_ME / DE421")
    fig.savefig(Path(root)/"figures"/f"{dem.source_id}_eda.png",dpi=130);plt.close(fig)
