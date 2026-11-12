"""Offline regression audit of Site01's 2026-11-17..27 sunlight using real NASA/JPL data.

Requires installed receipt-verified DEMs and the completed coordinate result.
Reads original code/data from the declared git revision. No generated ephemerides,
network calls, changes to production geometry, or acceptance-tolerance changes.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import types

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.mission.identity import digest
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.point_analysis.sources import TerrainInputs
from app.services.lunarsight.horizons import parse
from app.services.lunarsight.visibility import visibility


def git_bytes(revision, path):
    return subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=ROOT)


def xyz(lon, lat, radius):
    lon, lat = np.deg2rad(lon), np.deg2rad(lat)
    return np.stack((radius*np.cos(lat)*np.cos(lon), radius*np.cos(lat)*np.sin(lon),
                     radius*np.sin(lat)), axis=-1)


def independent_elevations(site, height, lon, lat, z):
    # Cartesian observer/terrain difference projected onto independently built ENU axes.
    l, p = np.deg2rad([site['lon_e_deg'], site['lat_deg']])
    basis = np.array([[-np.sin(l), np.cos(l), 0],
                      [-np.sin(p)*np.cos(l), -np.sin(p)*np.sin(l), np.cos(p)],
                      [np.cos(p)*np.cos(l), np.cos(p)*np.sin(l), np.sin(p)]])
    delta = xyz(lon, lat, 1737400.+np.asarray(z)) - xyz(site['lon_e_deg'], site['lat_deg'],
                                                            1737400.+site['dem_z_m']+height)
    enu = delta @ basis.T
    return np.rad2deg(np.arctan2(enu[..., 2], np.hypot(enu[..., 0], enu[..., 1])))


def scalar_horizons(profile, azimuths):
    rows = profile.to_dict('records')
    step = rows[0]['az_step_deg']
    output = []
    for az in azimuths:
        pos = (float(az) % 360) / step
        left = int(math.floor(pos)) % len(rows)
        frac = pos-math.floor(pos)
        a, b = rows[left], rows[(left+1) % len(rows)]
        assert a['coverage_complete'] and b['coverage_complete']
        output.append(a['horizon_deg']*(1-frac)+b['horizon_deg']*frac)
    return np.asarray(output)


def independent_raw(receipt, cache, start, end):
    raw = cache / receipt['raw_file']
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == receipt['sha256']
    payload = json.loads(raw.read_text())
    params = receipt['identity']['params']
    first = params['START_TIME'].strip("'")+'+00:00'
    last = params['STOP_TIME'].strip("'")+'+00:00'
    checked, meta, _ = parse(payload, params, first, last, receipt['step_minutes'], 1737400.)
    # Separate table reader deliberately bypasses the application's calendar and column parser.
    header, table = payload['result'].split('$$SOE')
    table = table.split('$$EOE')[0]
    names = next(csv.reader([next(line for line in header.splitlines() if 'Date__(UT)' in line and 'Azimuth_(a-app)' in line)]))
    names = [name.strip() for name in names]
    ia, ie = names.index('Azimuth_(a-app)'), names.index('Elevation_(a-app)')
    values = []
    for row in csv.reader(io.StringIO(table)):
        if not row or not row[0].strip():
            continue
        stamp = row[0].strip().removeprefix('A.D. ')
        fmt = '%Y-%b-%d %H:%M:%S' if stamp.count(':') == 2 else '%Y-%b-%d %H:%M'
        utc = datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc)
        values.append((utc, float(row[ia]), float(row[ie])))
    independent = pd.DataFrame(values, columns=['utc', 'az_deg', 'el_deg']).set_index('utc')
    assert independent.index.equals(checked.index)
    np.testing.assert_allclose(independent.to_numpy(), checked[['az_deg', 'el_deg']].to_numpy(), atol=1e-12, rtol=0)
    assert meta['missing_timestamps'] == meta['missing_angles'] == 0
    assert meta['observer_frame'].startswith('MEAN_ME')
    return checked.loc[start:end]


def audit(result_path, revision):
    supplied = json.loads(result_path.read_text())
    request = MissionRequest.model_validate(supplied['request'])
    assert request.start_utc == '2026-11-17T00:00:00Z' and request.duration_hours == 240
    cache = ROOT/'data/cache/point-analysis'
    pipeline = PointAnalysisPipeline(cache)
    # Audit the declared versioned artifact even when the current resolution
    # policy has a newer cache key. Terrain/raw/profile hashes are rechecked
    # below; do not relabel historical evidence as a newly computed result.
    result_directory = cache/'results'/supplied['result_id']
    receipt = json.loads((result_directory/'receipt.json').read_text())
    assert digest(receipt['identity']) == supplied['result_id']
    result = pipeline.cached_result(result_directory, receipt['identity'])
    assert result and result['request'] == supplied['request']
    original = types.ModuleType('app.services.lunarsight.original_visibility_audit')
    original.__package__ = 'app.services.lunarsight'
    exec(compile(git_bytes(revision, 'backend/app/services/lunarsight/visibility.py'), '<original visibility>', 'exec'), original.__dict__)
    unchanged = {}
    for path in ('backend/app/point_analysis/geometry.py', 'backend/app/services/lunarsight/horizon.py'):
        unchanged[path] = git_bytes(revision, path) == (ROOT/path).read_bytes()
        assert unchanged[path]
    tracked = 'data/processed/lunarsight/v0.3.0/visibility/Site01_intervals.csv'
    tracked_bytes = git_bytes(revision, tracked)
    assert tracked_bytes == (ROOT/tracked).read_bytes()
    old = pd.read_csv(io.BytesIO(tracked_bytes))
    selected = old[(pd.to_datetime(old.start_utc, utc=True) >= pd.Timestamp(request.start_utc)) &
                   (pd.to_datetime(old.end_utc, utc=True) <= pd.Timestamp(request.end_utc))]
    assert len(selected) == 2880 and selected.sun_state.eq('V').all()
    api_timeline = pd.DataFrame(result['timeline'])
    np.testing.assert_array_equal(selected.sun_el_deg.to_numpy(), api_timeline.sun_el_deg.to_numpy())
    np.testing.assert_array_equal(selected.sun_az_deg.to_numpy(), api_timeline.sun_az_deg.to_numpy())
    report = {'passed': False, 'baseline_revision': revision, 'result_id': result['result_id'],
              'request': request.model_dump(), 'coordinate': result['coordinate'],
              'artifact_resolution_policy': result['resolution']['policy_version'],
              'unchanged_geometry_source': unchanged,
              'original_tracked_intervals': {'path': tracked, 'sha256': hashlib.sha256(tracked_bytes).hexdigest(),
                  'byte_identical': True, 'intervals_in_requested_window': len(selected),
                  'sun_state_counts': selected.sun_state.value_counts().to_dict(),
                  'old_and_new_sun_ephemeris_angles_identical': True,
                  'max_horizon_difference_after_angular_refinement_deg': float(np.max(abs(
                      selected.sun_horizon_deg.to_numpy()-api_timeline.sun_horizon_deg.to_numpy())))},
              'native_grids': {}, 'jpl_raw_files': []}
    with TerrainInputs(request) as terrain:
        assert terrain.provenance() == result['provenance']['geometry']['identity']['datasets']
        receipt = result['provenance']['geometry']
        directory = cache/'geometry'/digest(receipt['identity'])
        profiles = {}
        xyz_checks = []
        for name, sha in receipt['files'].items():
            path = directory/name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
            profile = pd.read_csv(path)
            h = float(profile.height_m.iloc[0])
            independently_computed = independent_elevations(terrain.site, h,
                profile.blocker_lon_e_deg.to_numpy(), profile.blocker_lat_deg.to_numpy(), profile.blocker_z_m.to_numpy())
            error = float(np.max(abs(independently_computed-profile.horizon_deg)))
            assert error < 1e-5 and profile.coverage_complete.all()
            xyz_checks.append({'file': name, 'blockers_checked': len(profile), 'max_elevation_error_deg': error})
            profiles[name] = profile
        base = {h: profiles[f'fine_h{h:g}.csv'].iloc[::2].reset_index(drop=True).assign(
            az_step_deg=float(profiles[f'fine_h{h:g}.csv'].az_step_deg.iloc[0])*2)
            for h in (request.panel_height_m, request.antenna_height_m)}
        native = {}
        for step in (5, 1):
            targets = []
            for target in (10, 399):
                chunks = []
                for rec in result['provenance']['ephemerides']:
                    if rec['target'] == target and rec['step_minutes'] == step:
                        chunks.append(independent_raw(rec, cache, request.start_utc, request.end_utc))
                        report['jpl_raw_files'].append({'path': rec['raw_file'], 'sha256': rec['sha256'],
                            'target': target, 'step_minutes': step, 'observer_alt_km': rec['observer_alt_km'],
                            'observer_frame': rec['observer_frame'], 'signature': rec['signature']})
                frame = pd.concat(chunks).sort_index()
                frame = frame.loc[~frame.index.duplicated(keep='first')]
                assert frame.index.equals(pd.date_range(request.start_utc, request.end_utc, freq=f'{step}min'))
                targets.append(frame)
            before = original.visibility(*targets, base[request.panel_height_m], base[request.antenna_height_m])
            after = visibility(*targets, base[request.panel_height_m], base[request.antenna_height_m])
            pd.testing.assert_frame_equal(before, after.astype({key: object for key in after.select_dtypes('category').columns}), check_dtype=False)
            if step == 5:
                actual_timeline = pd.DataFrame(result['timeline'])
                for key in ('sun_el_deg', 'sun_az_deg', 'sun_horizon_deg', 'sun_clearance_deg',
                            'earth_el_deg', 'earth_horizon_deg'):
                    # Production records() rounds to ten decimal places; this
                    # checks serialization only, not the scientific tolerance.
                    np.testing.assert_allclose(actual_timeline[key], after[key], atol=5.1e-11, rtol=0)
                assert actual_timeline.sun_state.tolist() == after.sun_state.tolist()
            sun = targets[0].iloc[:-1]
            scalar = scalar_horizons(base[request.panel_height_m], sun.az_deg)
            clearance = sun.el_deg.to_numpy()-scalar
            np.testing.assert_allclose(clearance, after.sun_clearance_deg, atol=1e-12, rtol=0)
            assert np.all(clearance > 0) and before.sun_state.eq('V').all()
            critical = int(clearance.argmin())
            report['native_grids'][str(step)+'min'] = {'intervals': len(after), 'boundary_rows': len(targets[0]),
                'original_and_current_outputs_identical': True, 'independent_scalar_classification_identical': True,
                'matches_api_timeline': True if step == 5 else None,
                'sun_hours': float(len(after)*step/60), 'sun_elevation_min_deg': float(sun.el_deg.min()),
                'sun_elevation_max_deg': float(sun.el_deg.max()), 'min_sun_clearance_deg': float(clearance.min()),
                'min_clearance_utc': sun.index[critical].isoformat(),
                'sun_azimuth_first_last_deg': [float(sun.az_deg.iloc[0]), float(sun.az_deg.iloc[-1])],
                'horizon_min_max_deg': [float(scalar.min()), float(scalar.max())]}
            native[step] = sun
        report['independent_xyz_blocker_checks'] = xyz_checks
        # Fresh, denser radial scans at 12 mission bearings, including the worst clearance.
        # This does not call ray_positions, ray_elevation, scan_horizons or lookup.
        sun = native[1]
        critical = int((sun.el_deg.to_numpy()-scalar_horizons(base[request.panel_height_m], sun.az_deg)).argmin())
        indices = sorted(set([critical, *np.linspace(0, len(sun)-1, 11, dtype=int)]))
        distance = np.r_[np.arange(2.5, 8000.01, 2.5), np.arange(8020, 200000.01, 20), np.arange(200060, 400000.01, 60)]
        lat1, lon1 = np.deg2rad([terrain.site['lat_deg'], terrain.site['lon_e_deg']])
        delta = distance/1737400.
        fresh = []
        for i in indices:
            az = float(sun.az_deg.iloc[i]); bearing = math.radians(az)
            lat = np.arcsin(np.sin(lat1)*np.cos(delta)+np.cos(lat1)*np.sin(delta)*np.cos(bearing))
            lon = lon1 + np.arctan2(np.sin(bearing)*np.sin(delta)*np.cos(lat1), np.cos(delta)-np.sin(lat1)*np.sin(lat))
            longitude, latitude = np.rad2deg(lon)%360, np.rad2deg(lat)
            z = np.full(len(distance), np.nan)
            for mask, resolution in ((distance<=8000, 0), ((distance>8000)&(distance<=200000), 80), (distance>200000, 240)):
                z[mask], _ = terrain.sample(longitude[mask], latitude[mask], resolution)
            assert np.isfinite(z).all()
            elevations = independent_elevations(terrain.site, request.panel_height_m, longitude, latitude, z)
            horizon = float(elevations.max()); clearance = float(sun.el_deg.iloc[i]-horizon)
            assert clearance > 0
            fresh.append({'utc': sun.index[i].isoformat(), 'azimuth_deg': az, 'radial_samples': len(distance),
                          'sun_elevation_deg': float(sun.el_deg.iloc[i]), 'fresh_horizon_deg': horizon,
                          'clearance_deg': clearance, 'visible': True})
        report['fresh_dem_xyz_rays'] = fresh
        report['verified_nasa_datasets'] = terrain.provenance()
    negative = json.loads((cache/'results/72fe0a9d21aa3c0a567b40909a90d4c77afc7456c0e0fd72f4fb159f1902b57f/result.json').read_text())
    directory = cache/'results'/negative['result_id']
    stored = pipeline.cached_result(directory, negative['provenance']['identity'])
    assert stored['decision'] == 'FAIL' and stored['metrics_hours']['total_sun_hours'] == [0., 0.]
    # Classify the negative control again with the original visibility implementation.
    timeline = pd.DataFrame(stored['timeline'])
    expected = original.classify(timeline.sun_el_deg, timeline.sun_horizon_deg, timeline.sun_terrain_complete)
    assert np.all(expected == 'B')
    report['negative_control'] = {'result_id': stored['result_id'], 'coordinate': stored['coordinate'],
        'start_utc': stored['request']['start_utc'], 'end_utc': stored['end_utc'],
        'decision': stored['decision'], 'total_sun_hours': stored['metrics_hours']['total_sun_hours'],
        'original_classifier_all_blocked': True, 'intervals': len(timeline)}
    report['mission_path_validation'] = result['validation']['mission_path']
    report['full_validation_passed'] = result['validation']['passed']
    report['remaining_validation_reasons'] = result['validation']['reason_codes']
    report['scope'] = 'Real-input regression and independent numerical checks; not independent observational ground truth.'
    report['limitations'] = ['Sun centre line of sight; not panel power or constant irradiance.',
        'Native 1-minute samples and 12 fresh denser rays do not certify every continuous instant.',
        'Global numerical gate remains failed; empirical mission-path envelope is provisional.',
        'NASA polar illumination averages support plausibility, not this particular date/coordinate prediction.']
    report['passed'] = True
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--baseline', default='94b33c68032f3561b6cd636bcf39384501bf6e34')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.result, args.baseline)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('passed', 'original_tracked_intervals', 'native_grids',
        'independent_xyz_blocker_checks', 'negative_control', 'full_validation_passed')}, indent=2))
