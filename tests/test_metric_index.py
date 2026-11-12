"""Indexed aggregates must preserve native unknown bounds and cross-day runs."""
import numpy as np
import pandas as pd
import pytest

from app.core.errors import DomainError
from app.mission.evaluation import metrics
from app.point_analysis.physics_cache import PhysicalSeriesCache
from app.point_analysis.prepared_metrics import PreparedMetrics
from app.point_analysis import metric_index
from app.services.lunarsight.durations import combine


def test_daily_index_matches_native_metrics_without_loading_timeline(tmp_path, monkeypatch):
    import app.point_analysis.physics_cache as module
    starts = pd.date_range("2026-11-17T00:00:00Z", periods=40*24*12, freq="5min")
    rng = np.random.default_rng(6)
    sun = rng.choice(["V", "B", "?"], len(starts))
    earth = rng.choice(["V", "B", "?"], len(starts))
    sun[200:900], earth[400:1700] = "B", "?"
    frame = pd.DataFrame({"start_utc": starts, "end_utc": starts+pd.Timedelta(minutes=5),
        "sun_state": sun, "earth_state": earth, "joint_state": combine(sun, earth),
        "sun_visible_fraction_lower": np.where(sun == "V", .375, 0.),
        "sun_visible_fraction_upper": np.where(sun == "V", .375, np.where(sun == "?", 1., 0.))})
    cache, source = PhysicalSeriesCache(tmp_path), {"explicit_synthetic": True}
    cache.save(source, frame, [], index=True)
    monkeypatch.setattr(module, "read_array", lambda *a: pytest.fail("summary scanned native timeline"))
    for a, b in [(0, 40), (0, 8), (1, 6), (2, 3), (0, 4), (3, 8)]:
        begin, end = starts[0]+pd.Timedelta(days=a), starts[0]+pd.Timedelta(days=b)
        subset = frame[(frame.start_utc >= begin)&(frame.end_utc <= end)]
        result = cache.summary(source, begin, end)
        for key, bounds in metrics(subset).items():
            assert result["metrics_hours"][key] == pytest.approx(bounds, abs=1e-9)
        dt = (subset.end_utc-subset.start_utc).dt.total_seconds().to_numpy()/3600
        assert result["joint_hours"] == pytest.approx([dt[subset.joint_state.eq("V")].sum(), dt[~subset.joint_state.eq("B")].sum()], abs=1e-9)
        assert result["source_intervals"] == len(subset)
        rows = result["timeline"]
        assert 0 < len(rows) <= 800 and all(row["aggregated"] for row in rows)
        assert not result["timeline_transport"]["exact_intervals_ready"]
        assert sum(row["source_intervals"] for row in rows) == len(subset)
        weights = np.array([(pd.Timestamp(row["end_utc"])-pd.Timestamp(row["start_utc"])).total_seconds()/3600 for row in rows])
        for body, expected in [("sun", result["metrics_hours"]["total_sun_hours"]),
                               ("earth", result["metrics_hours"]["total_earth_los_hours"]), ("joint", result["joint_hours"])]:
            integrated = [np.dot(weights, [row[body+"_visible_fraction_"+bound] for row in rows]) for bound in ("lower", "upper")]
            assert integrated == pytest.approx(expected, abs=1e-8)
    assert cache.summary(source, starts[1], starts[-1]) is None
    assert cache.summary(source, starts[0], starts[-1]+pd.Timedelta(days=1)) is None
    assert cache.summary({"explicit_synthetic": False}, starts[0], starts[-1]) is None
    next(cache.root.glob("*/*/metrics.npz")).write_bytes(b"corrupted")
    with pytest.raises(DomainError, match="PHYSICAL_METRICS_INTEGRITY_FAILED"):
        cache.summary(source, starts[0], frame.end_utc.iloc[-1])


def test_compact_year_parts_preserve_cross_year_runs_without_native_archive(tmp_path):
    starts = pd.date_range("1999-12-31T00:00:00Z", "2000-01-04T00:00:00Z", freq="1h", inclusive="left")
    sun, earth = np.full(len(starts), "V"), np.full(len(starts), "V")
    sun[18:54], earth[20:36] = "B", "?"
    frame = pd.DataFrame({"start_utc": starts, "end_utc": starts+pd.Timedelta(hours=1),
        "sun_state": sun, "earth_state": earth, "joint_state": combine(sun, earth),
        "sun_visible_fraction_lower": (sun == "V")*.5, "sun_visible_fraction_upper": (sun == "V")*.5})
    first = frame[frame.end_utc <= pd.Timestamp("2000-01-01T00:00:00Z")]
    second = frame[frame.start_utc >= pd.Timestamp("2000-01-01T00:00:00Z")]
    parts = [metric_index.build(part)[0] for part in (first, second)]
    content, full = metric_index.combine_parts(iter(parts))
    store, source = PreparedMetrics(tmp_path), {"synthetic_year_parts": True}
    directory = store.publish(source, frame.start_utc.iloc[0], frame.end_utc.iloc[-1], content, full, [{"synthetic": True}])
    assert not list(tmp_path.rglob("timeline.npy"))
    for a, b in [("1999-12-31", "2000-01-04"), ("1999-12-31", "2000-01-02"), ("2000-01-01", "2000-01-03")]:
        begin, end = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        result = store.query(source, begin, end)
        subset = frame[(frame.start_utc >= begin)&(frame.end_utc <= end)]
        for name, pair in metrics(subset).items():
            assert result["metrics_hours"][name] == pytest.approx(pair, abs=1e-9)
        assert result["physical_series_cache_hit"] is False
        assert result["source"]["kind"] == "prepared_metrics_only"
        assert PhysicalSeriesCache(tmp_path).summary(source, begin, end)["metrics_hours"] == result["metrics_hours"]
    assert full["longest_dark_hours"] == [36, 36]
    assert store.query(source, "1999-12-30T00:00:00Z", "2000-01-03T00:00:00Z") is None
    assert store.query({"synthetic_year_parts": False}, "1999-12-31T00:00:00Z", "2000-01-03T00:00:00Z") is None
    with pytest.raises(ValueError, match="not contiguous"):
        metric_index.combine_parts([parts[1], parts[0]])
    (directory/"metrics.npz").write_bytes(b"corrupt")
    with pytest.raises(DomainError, match="PHYSICAL_METRICS_INTEGRITY_FAILED"):
        store.query(source, "1999-12-31T00:00:00Z", "2000-01-03T00:00:00Z")


def test_short_prepared_query_uses_verified_part_instead_of_large_aggregate(tmp_path, monkeypatch):
    from app.mission.identity import digest
    from app.point_analysis.pipeline import atomic_json
    from app.point_analysis.prepared_metrics import atomic_bytes
    from app.services.lunarsight.acquire import hashfile
    starts = pd.date_range("2000-01-01T00:00:00Z", periods=48, freq="1h")
    frame = pd.DataFrame({"start_utc": starts, "end_utc": starts+pd.Timedelta(hours=1),
        "sun_state": "V", "earth_state": "B", "joint_state": "B"})
    source, store = {"synthetic_part_lookup": True}, PreparedMetrics(tmp_path)
    contents, chunks = [], []
    for a, b in [(0, 24), (24, 48)]:
        part = frame.iloc[a:b]
        coverage = {"start_utc": part.start_utc.iloc[0].isoformat(), "end_utc": part.end_utc.iloc[-1].isoformat()}
        directory = store.root/digest(source)/".parts"/digest(coverage)
        content, full = metric_index.build(part)
        atomic_bytes(directory/"metrics.npz", content)
        reference = {"version": metric_index.VERSION, "sha256": hashfile(directory/"metrics.npz"), "full_metrics": full}
        atomic_json(directory/"receipt.json", {"identity_sha256": digest(source), **coverage, "metrics_index": reference})
        chunks.append({**coverage, "receipt_sha256": hashfile(directory/"receipt.json"), "index_sha256": reference["sha256"]})
        contents.append(content)
    combined, full = metric_index.combine_parts(contents)
    store.publish(source, frame.start_utc.iloc[0], frame.end_utc.iloc[-1], combined, full, chunks)
    read = metric_index._read
    def only_part(path, *args):
        assert "/.parts/" in path, "Short query decompressed the entire long-range index"
        return read(path, *args)
    monkeypatch.setattr(metric_index, "_read", only_part)
    result = store.query(source, "2000-01-02T00:00:00Z", "2000-01-03T00:00:00Z")
    assert result["metrics_hours"]["total_sun_hours"] == [24, 24]
    assert result["source"]["index_sha256"] == chunks[-1]["index_sha256"]
    (directory/"receipt.json").write_text("{}")
    with pytest.raises(DomainError, match="PREPARED_METRICS_INTEGRITY_FAILED"):
        store.query(source, "2000-01-02T00:00:00Z", "2000-01-03T00:00:00Z")
