import math
import numpy as np
import pandas as pd
from .terrain import R

def enu_basis(lon,lat):
    l,p=np.deg2rad([lon,lat]); sl,cl=np.sin(l),np.cos(l); sp,cp=np.sin(p),np.cos(p)
    return np.array([[-sl,cl,0],[-sp*cl,-sp*sl,cp],[cp*cl,cp*sl,sp]])

def point_xyz(lon,lat,z):
    return (R+z)*enu_basis(lon,lat)[2]

def angles_enu(lon,lat,z0,h,lonq,latq,zq):
    v=point_xyz(lonq,latq,zq)-point_xyz(lon,lat,z0+h)
    e,n,u=enu_basis(lon,lat)@v
    return float(np.rad2deg(np.arctan2(e,n))%360),float(np.rad2deg(np.arctan2(u,np.hypot(e,n))))

def ray_positions(lon,lat,az_deg,dist):
    az=np.deg2rad(np.asarray(az_deg)); delta=np.atleast_2d(dist)/R
    e,n,u=enu_basis(lon,lat)
    t=np.sin(az)[:,None]*e+np.cos(az)[:,None]*n
    q=np.cos(delta)[...,None]*u+np.sin(delta)[...,None]*t[:,None,:]
    lonq=np.rad2deg(np.arctan2(q[:,:,1],q[:,:,0]))
    latq=np.rad2deg(np.arctan2(q[:,:,2],np.hypot(q[:,:,0],q[:,:,1])))
    return lonq,latq

def ray_elevation(z,z0,h,dist):
    delta=np.asarray(dist)/R; radius=R+np.asarray(z)
    # Use cos(d)-1 = -2 sin²(d/2) to avoid cancellation in the near field.
    up=np.asarray(z)-z0-h-2*radius*np.sin(delta/2)**2
    return np.rad2deg(np.arctan2(up,radius*np.sin(delta)))

def ranges(spec,radius):
    # Avoid a gap bigger than the allowed spacing at each resolution seam.
    left=0.
    for label,stop,spacing in spec:
        end=min(float(stop),float(radius))
        if end<=left: break
        n=math.ceil((end-left)/spacing)
        yield label,np.linspace(left,end,n+1)[1:]
        left=end
    if left!=radius: raise ValueError("Radius outside configured rings")

def footprint_radius(site,dem,az_deg,margin=275.):
    """First exit from the inset 5 m bounding rectangle along each great-circle ray."""
    lon,lat=site["lon_e_deg"],site["lat_deg"]; bb=dem.ds.bounds
    def inside(d):
        l,p=ray_positions(lon,lat,az_deg,d[:,None]); x,y=dem.fwd.transform(l[:,0],p[:,0])
        return (x>bb.left+margin)&(x<bb.right-margin)&(y>bb.bottom+margin)&(y<bb.top-margin)
    left=np.zeros(len(az_deg)); right=np.full(len(az_deg),30000.)
    if not inside(left).all() or inside(right).any(): raise ValueError("Failed to bracket fine DEM footprint")
    for _ in range(23):
        mid=(left+right)/2; keep=inside(mid)
        left=np.where(keep,mid,left); right=np.where(keep,right,mid)
    return np.floor(left/2.5)*2.5

def profile(site,dems,height,az_step,spec,radius,footprint_margin=None):
    if az_step not in (.25,.125): raise ValueError("Unsupported azimuth step")
    lon,lat,z0=site["lon_e_deg"],site["lat_deg"],site["dem_z_m"]
    azs=np.arange(0,360,az_step)
    pieces=list(ranges(spec,radius))
    near_cut=(np.full(len(azs),spec[0][1]) if footprint_margin is None else footprint_radius(site,dems["5m"],azs,footprint_margin))
    rows=[]
    for i in range(0,len(azs),32):
        az=azs[i:i+32]
        n=len(az); best=np.full(n,-np.inf); br=np.full(n,np.nan); bz=np.full(n,np.nan)
        blon=np.full(n,np.nan); blat=np.full(n,np.nan); bsrc=np.full(n,"",dtype=object)
        missing=np.zeros(n,dtype=int); fallback=np.zeros(n,dtype=int); valid=np.zeros(n,dtype=int)
        used=np.zeros((n,3),int)
        order=list(dems)
        near=near_cut[i:i+n]
        for label,dist in pieces:
            j=order.index(label)
            active=None
            if footprint_margin is not None and j==0:
                dist=np.arange(spec[0][2],near.max()+.01,spec[0][2])
                active=dist[None,:]<=near[:,None]
            elif footprint_margin is not None and j==1:
                limit=min(radius,spec[1][1]); steps=np.ceil((limit-near)/spec[1][2]).astype(int)
                if (steps<1).any(): raise ValueError("Scan radius inside fine footprint seam")
                i_step=np.arange(1,steps.max()+1)
                active=i_step[None,:]<=steps[:,None]
                dist=near[:,None]+(limit-near)[:,None]*i_step[None,:]/steps[:,None]
            x,y=ray_positions(lon,lat,az,dist)
            if active is None: active=np.ones(x.shape,dtype=bool)
            z=np.full(x.shape,np.nan)
            z[active]=dems[label].lonlat_at(x[active],y[active])
            layer=np.full(z.shape,j,dtype=np.int8)
            for k in range(j+1,len(order)):
                masked=active&~np.isfinite(z)
                if not np.any(masked): break
                alt=dems[order[k]].lonlat_at(x[masked],y[masked])
                z[masked]=alt; layer[masked]=k
            finite=np.isfinite(z)
            fallback+=np.sum(finite&(layer!=j),axis=1); valid+=finite.sum(axis=1); missing+=(active&~finite).sum(axis=1)
            for k in range(len(order)): used[:,k]+=np.sum(finite&(layer==k),axis=1)
            el=np.where(finite,ray_elevation(z,z0,height,dist),-np.inf)
            winner=np.argmax(el,axis=1); value=el[np.arange(n),winner]
            take=np.flatnonzero(value>best); win=winner[take]
            best[take]=value[take]; br[take]=np.broadcast_to(dist,z.shape)[take,win]; bz[take]=z[take,win]
            blon[take]=x[take,win]%360; blat[take]=y[take,win]; bsrc[take]=np.array(order)[layer[take,win]]
        for k,a in enumerate(az):
            rows.append(dict(site_id=site["site_id"],az_deg=a,az_step_deg=az_step,height_m=height,
                horizon_deg=best[k] if np.isfinite(best[k]) else np.nan,
                blocker_distance_m=br[k],blocker_z_m=bz[k],blocker_lon_e_deg=blon[k],blocker_lat_deg=blat[k],
                blocker_source=bsrc[k],scan_radius_m=radius,missing_samples=missing[k],
                near_switch_radius_m=near[k],near_switch_strategy="footprint" if footprint_margin is not None else "fixed",
                valid_samples=valid[k],fallback_samples=fallback[k],coverage_complete=missing[k]==0,
                samples_5m=used[k,0],samples_80m=used[k,1],samples_240m=used[k,2]))
    return pd.DataFrame(rows)

def seam_diagnostics(site,dems,spec,footprint_margin=None,phase=0.):
    """Paired DEM values across ±250 m of nominal switch; no offset is fit."""
    az=np.arange(phase,360,.5); out=[]
    lon,lat=site["lon_e_deg"],site["lat_deg"]
    for (fine,r,_),(coarse,_,_) in zip(spec,spec[1:]):
        radii=footprint_radius(site,dems[fine],az,footprint_margin) if fine=="5m" and footprint_margin is not None else np.full(len(az),r)
        ds=radii[:,None]+np.linspace(-250,250,11)
        l,p=ray_positions(lon,lat,az,ds)
        a=dems[fine].lonlat_at(l,p); b=dems[coarse].lonlat_at(l,p)
        d=b-a; v=d[np.isfinite(d)]
        angular=ray_elevation(b,site["dem_z_m"],1,ds)-ray_elevation(a,site["dem_z_m"],1,ds)
        ok=angular[np.isfinite(angular)]
        for ai,t in enumerate(az):
            for di,di_m in enumerate(ds[ai]):
                out.append(dict(fine=fine,coarse=coarse,switch_m=radii[ai],az_deg=t,distance_m=di_m,
                    fine_z_m=a[ai,di],coarse_z_m=b[ai,di],delta_coarse_minus_fine_m=d[ai,di],
                    el_difference_deg=angular[ai,di]))
        yield dict(fine=fine,coarse=coarse,switch_min_m=float(radii.min()),switch_max_m=float(radii.max()),
                   azimuth_phase_deg=phase,method="footprint" if fine=="5m" and footprint_margin is not None else "fixed",paired=int(len(v)),sampled=int(d.size),
                   median_signed_m=float(np.median(v)) if len(v) else None,
                   p95_abs_m=float(np.percentile(abs(v),95)) if len(v) else None,
                   p95_abs_angle_deg=float(np.percentile(abs(ok),95)) if len(ok) else None),pd.DataFrame(out)
        out=[]

def reference_check(profile,site):
    """Recompute decisive elevations with the independent XYZ→ENU path."""
    diffs=[]; da=[]
    for _,row in profile[np.isfinite(profile.horizon_deg)].iloc[::17].iterrows():
        a,e=angles_enu(site["lon_e_deg"],site["lat_deg"],site["dem_z_m"],row.height_m,
                       row.blocker_lon_e_deg,row.blocker_lat_deg,row.blocker_z_m)
        diffs.append(abs(e-row.horizon_deg)); da.append(abs((a-row.az_deg+180)%360-180))
    if not diffs or max(diffs)>1e-5 or max(da)>1e-5: raise ValueError("Real blocker ENU reference check failed")
    return dict(checks=len(diffs),max_delta_el_deg=max(diffs),max_delta_az_deg=max(da))
