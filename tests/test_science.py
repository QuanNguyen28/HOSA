from itertools import product
from pathlib import Path
from datetime import timezone
import json
import math
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from backend.app.services.lunarsight.terrain import DEM, R
from backend.app.services.lunarsight.horizon import angles_enu, ray_positions, ray_elevation, ranges, profile, reference_check
from backend.app.services.lunarsight.horizons import parse, request_params, timestamp
from backend.app.services.lunarsight.visibility import classify, combine, lookup, bounds, max_rule, valid_start, visibility, analyze

CASES=json.loads((Path(__file__).parent/"fixtures/synthetic_cases.json").read_text())

def test_t01_t03_mask_scale_affine(tmp_path):
    p=tmp_path/"synthetic_lunar.tif"
    crs="+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +type=crs"
    with rasterio.open(p,"w",driver="GTiff",height=2,width=3,count=1,dtype="int16",
        crs=crs,transform=from_origin(-15,10,5,5),nodata=-32768) as ds:
        ds.write(np.array([[0,2,8],[10,-32768,30]],dtype=np.int16),1)
        ds.scales=(.5,);ds.offsets=(100,)
    with DEM(p,"synthetic") as d:
        np.testing.assert_allclose(d.xy_at([-12.5,-7.5,-2.5,-7.5,0],[7.5,7.5,7.5,2.5,2.5]),
                                   [100,101,104,np.nan,np.nan],equal_nan=True)
        lon,lat=d.inv.transform(-12.5,7.5)
        assert d.lonlat_at(lon,lat)==100
        assert d.ds.index(*d.fwd.transform(lon,lat))==(0,0)

@pytest.mark.parametrize("az",CASES["cardinal_obstacle"]["azimuths_deg"])
def test_t04_cardinal_enu_known_angle(az):
    lon,lat=222,-89.4; d=1000.; delta=d/R; h=1.; target=5.
    # Solve the independently specified 3D angular intersection analytically for obstacle radius.
    z=(R+h)/(math.cos(delta)-math.sin(delta)*math.tan(math.radians(target)))-R
    l,p=ray_positions(lon,lat,[az],[d]); a,e=angles_enu(lon,lat,0,h,l[0,0],p[0,0],z)
    assert abs((a-az+180)%360-180)<1e-8
    assert e==pytest.approx(target,abs=1e-8)
    assert ray_elevation(z,0,h,d)==pytest.approx(target,abs=1e-8)

def test_t04_obstacle_detected_by_profile():
    lon,lat=222,-89.4
    lo,la=ray_positions(lon,lat,[90],[1000])
    class AnalyticTerrain:
        def lonlat_at(self,l,p):
            return np.where((abs(l-lo[0,0])<1e-7)&(abs(p-la[0,0])<1e-7),101.,0.)
    dems={k:AnalyticTerrain() for k in ("5m","80m","240m")}
    site=dict(site_id="SYNTH",lon_e_deg=lon,lat_deg=lat,dem_z_m=0)
    p=profile(site,dems,1,.25,[("5m",1000,2.5),("80m",2000,40),("240m",3000,120)],3000)
    winner=p.loc[p.horizon_deg.idxmax()]
    assert winner.az_deg==90 and winner.blocker_distance_m==1000 and winner.blocker_source=="5m"
    assert p.loc[p.az_deg.isin([0,180,270]),"horizon_deg"].max()<0
    assert reference_check(p,site)["max_delta_el_deg"]<1e-7

def test_t05_sphere_curvature_only_once_and_seam_spacing():
    d=150_000
    assert ray_elevation(0,0,0,d)==pytest.approx(-math.degrees(d/R)/2,abs=1e-10)
    prev=0
    spec=[("5m",999,2.5),("80m",2233,40),("240m",4090,120)]
    for (_,dist),(_,_,limit) in zip(ranges(spec,3333),spec):
        assert np.diff(np.r_[prev,dist]).max()<=limit+1e-9
        prev=dist[-1]
    assert prev==3333

def fixture(rows):
    h="""Target body name: Sun (10) {source: DE441}
Center body name: Moon (301)
Center pole/equ : MEAN_ME (high precision) {East-longitude positive}
Center geodetic : 220.0, -89.5, 1.001 {E-lon(deg),Lat(deg),Alt(km)}
Center radii    : 1737.4, 1737.4, 1737.4 km
Atmos refraction: NO (AIRLESS)
Start time      : A.D. 2026-Nov-14 00:00:00.0000 UT
Stop  time      : A.D. 2026-Nov-14 00:10:00.0000 UT
Step-size       : 5 minutes
 Date__(UT)__HR:MN:SS, , ,Azimuth_(a-app), Elevation_(a-app),
"""
    return {"signature":{"version":"1.2"},"result":h+"$$SOE\n"+rows+"\n$$EOE\nTimes AFTER 1962 are in UTC. Units: DEGREES"}
def test_t06_t07_horizons_parser_and_missing():
    a=pd.Timestamp("2026-11-14T00:00:00Z"); b=a+pd.Timedelta(minutes=10)
    kw=request_params(10,220,-89.5,1000,1,R,R,a,b,5)
    good="2026-Nov-14 00:00:00,*, , 359.95, 2,\n2026-Nov-14 00:10:00,*, , 0.05, n.a.,"
    df,m,_=parse(fixture(good),kw,a,b,5,R)
    assert str(df.index.tz)=="UTC" and len(df)==3
    assert m["missing_timestamps"]==1 and m["missing_angles"]==2
    assert not df.iloc[1].row_present and np.isnan(df.iloc[2].el_deg)
    dup=good.replace("00:10:00","00:00:00")
    with pytest.raises(ValueError,match="duplicate"): parse(fixture(dup),kw,a,b,5,R)
    with pytest.raises(ValueError,match="shape"): parse(fixture(good),kw,a,b,5,R+1000)
    assert request_params(10,220,-89.5,1000,1,R,R-100,a,b,5)["SITE_COORD"].endswith(",1.101000000'")

def test_horizons_timestamp_accepts_minute_precision_from_live_api():
    assert timestamp(" 2026-Apr-02 02:20") == pd.Timestamp("2026-04-02T02:20:00Z")

def test_horizons_minute_precision_calendar_keeps_grid_validation():
    a=pd.Timestamp("2026-11-14T00:00:00Z"); b=a+pd.Timedelta(minutes=10)
    kw=request_params(10,220,-89.5,1000,1,R,R,a,b,5)
    rows="2026-Nov-14 00:00,*, , 359.95, 2,\n2026-Nov-14 00:05,*, , 0, 2,\n2026-Nov-14 00:10,*, , 0.05, 2,"
    df,meta,_=parse(fixture(rows),kw,a,b,5,R)
    assert df.index.equals(pd.date_range(a,b,freq='5min'))
    assert meta['missing_timestamps']==meta['missing_angles']==0
    with pytest.raises(ValueError,match='off-grid'):
        parse(fixture(rows.replace('00:05','00:07')),kw,a,b,5,R)

def test_t08_t13_last_start_and_terminal_boundary():
    a=pd.Timestamp("2026-11-14T00:00:00Z");b=a+pd.Timedelta(days=14)
    last=valid_start(a,b,1343)
    assert last==b-pd.Timedelta(minutes=15)
    for k in [-1,1344,.5,True]:
        with pytest.raises(ValueError): valid_start(a,b,k)
    end=b+pd.Timedelta(hours=72)
    assert len(pd.date_range(a,end,freq="5min"))==4897
    t=pd.date_range(last,last+pd.Timedelta(hours=72),freq="5min")
    p=pd.DataFrame(dict(az_deg=np.arange(0,360,.25),az_step_deg=.25,horizon_deg=1.,coverage_complete=True))
    s=pd.DataFrame(dict(az_deg=80.,el_deg=2.,row_present=True),index=t)
    v=visibility(s,s,p,p)
    assert len(v)==864 and v.end_utc.iloc[-1]==t[-1]
    assert analyze(v,last,0,0)[2]=="PASS"
    with pytest.raises(ValueError,match="gaps"): analyze(v.drop(v.index[3]),last,0,0)

def test_t09_unknown_wrap_and_exact_block():
    p=pd.DataFrame(dict(az_deg=[0,90,180,270],az_step_deg=90,horizon_deg=[2.,2.,4.,6.],coverage_complete=[True,False,True,True]))
    h,cov=lookup(p,[315,45,90,180,np.nan])
    assert classify([5,1,2,np.nan,3],h,cov).tolist()==["V","?","B","?","?"]
    assert classify([2,3],[2,2],[True,False]).tolist()==["B","?"]

def test_t10_all_nine_and_cases():
    cases=list(product("VB?","VB?"))
    s,e=zip(*cases)
    assert "".join(combine(s,e))=="VB?BBB?B?"

@pytest.mark.parametrize("case",CASES["duration_cases"])
def test_t11_nonuniform_and_unknown_bounds(case):
    m=bounds(list(case["s"]),list(case["e"]),case["hours"])
    assert m["total_sun_hours"]==case["sun"]
    assert m["longest_dark_hours"]==case["dark"]
    assert m["longest_blackout_hours"]==case["blackout"]
    assert m["longest_joint_hours"]==case["joint"]

def test_t12_t15_limits():
    assert [max_rule([2,4],x) for x in (1,2,4)]==["FAIL","INDETERMINATE","PASS"]
    for m in (-1,73,float("nan"),float("inf"),True):
        with pytest.raises(ValueError): max_rule([1,2],m)


def event_frame(step, blocked):
    start=pd.Timestamp('2026-11-17T00:00:00Z')
    grid=pd.date_range(start,periods=60//step+1,freq=f'{step}min')
    states=['B' if any(a<=i*step<b for a,b in blocked) else 'V' for i in range(len(grid)-1)]
    return pd.DataFrame({'start_utc':grid[:-1],'end_utc':grid[1:],'earth_state':states})


def test_event_matching_never_reuses_a_boundary():
    from backend.app.services.lunarsight.visibility import sensitivity, match_events
    first=event_frame(5,[(5,10),(15,20)])
    second=event_frame(1,[(10,15),(24,29)])
    result=sensitivity(first,second,['earth_state'])['earth_state']
    assert result['events_first']==result['events_second']==4
    assert result['matched_first_within_15min']==4
    assert result['max_matched_event_shift_minutes']==9
    left,right,pairs=match_events(first.set_index('start_utc').earth_state,
                                  second.set_index('start_utc').earth_state)
    assert len({a for a,b,s in pairs})==len(pairs)
    assert len({b for a,b,s in pairs})==len(pairs)
    assert pairs==sorted(pairs)


def test_event_matching_reports_unmatched_boundaries_on_both_sides():
    from backend.app.services.lunarsight.visibility import sensitivity
    first=event_frame(5,[(5,10)])
    second=event_frame(1,[(40,45)])
    result=sensitivity(first,second,['earth_state'])['earth_state']
    assert result['matched_first_within_15min']==0
    assert result['unmatched_first']==result['unmatched_second']==2
    assert result['max_matched_event_shift_minutes'] is None
