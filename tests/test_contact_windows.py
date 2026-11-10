"""Contact-window semantics independent of the expensive terrain pipeline."""
from datetime import datetime, timedelta, timezone
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.contact_windows import analyze_contacts


START = datetime(2026, 11, 14, tzinfo=timezone.utc)


def payload(states, lengths=None, validated=True):
    lengths = lengths or [1] * len(states)
    cursor, rows = START, []
    for state, length in zip(states, lengths):
        end = cursor + timedelta(minutes=length)
        rows.append({"start_utc": cursor.isoformat(), "end_utc": end.isoformat(), "earth_state": state})
        cursor = end
    return {"request": {"start_utc": START.isoformat()}, "end_utc": cursor.isoformat(),
            "timeline": rows, "validation": {"passed": validated}, "decision": "INDETERMINATE"}


def test_same_total_los_different_usable_windows():
    fragmented = analyze_contacts(payload("VB" * 60), min_contact_minutes=20)
    continuous = analyze_contacts(payload("VB", [60, 60]), min_contact_minutes=20)
    assert fragmented["metrics"]["total_los_minutes_bounds"] == continuous["metrics"]["total_los_minutes_bounds"] == [60, 60]
    assert fragmented["metrics"]["qualified_windows_count"] == 0
    assert continuous["metrics"]["qualified_windows_count"] == 1
    assert fragmented["requirements"]["decision"] == "FAIL"
    assert continuous["requirements"]["decision"] == "PASS"


def test_weighted_intervals_clipping_and_terminal_boundary():
    data = payload("BVVBBV", [2, 3, 7, 1, 4, 2])
    result = analyze_contacts(data, start_utc=(START + timedelta(minutes=1)).isoformat(),
                              end_utc=(START + timedelta(minutes=18)).isoformat(), min_contact_minutes=10)
    assert [w["duration_minutes"] for w in result["visible_windows"]] == [10, 1]
    assert result["metrics"]["total_los_minutes_bounds"] == [11, 11]
    assert result["metrics"]["max_gap_minutes_bounds"] == [5, 5]
    assert result["metrics"]["first_contact_wait_minutes"] == {"earliest_possible": 1, "first_confirmed": 1}
    assert result["visible_windows"][-1]["touches_window_end"] is True
    assert result["visible_windows"][-1]["outside_window_duration_known"] is False


def test_unknown_does_not_join_confirmed_windows_or_claim_count_bound():
    result = analyze_contacts(payload("V?V", [20, 5, 20]), min_contact_minutes=20, required_windows=2)
    assert len(result["visible_windows"]) == 2
    assert result["metrics"]["longest_contact_minutes_bounds"] == [20, 45]
    assert result["metrics"]["qualified_windows_count_complete"] is False
    # Resolving ? to V merges both runs, so two observed runs are not a guaranteed count.
    assert result["requirements"]["sampled_checks"]["required_windows"] == "INDETERMINATE"


def test_missing_rows_and_leading_trailing_gaps_are_unknown():
    data = payload("VVVVV")
    data["timeline"] = [data["timeline"][1], data["timeline"][3]]
    result = analyze_contacts(data)
    assert result["sampling"]["unknown_minutes_including_gaps"] == 3
    assert len(result["unknown_intervals"]) == 3
    assert result["metrics"]["longest_contact_minutes_bounds"] == [1, 5]
    assert result["metrics"]["first_contact_wait_minutes"] == {"earliest_possible": 0, "first_confirmed": 1}


def test_setup_and_deadline_require_session_completion():
    data = payload("BV", [10, 30])
    result = analyze_contacts(data, min_contact_minutes=20, setup_minutes=5,
                              required_windows=1, first_contact_deadline_minutes=35, max_gap_minutes=10)
    assert result["requirements"]["decision"] == "PASS"
    assert result["metrics"]["qualified_visible_minutes"] == 25
    assert analyze_contacts(data, min_contact_minutes=20, setup_minutes=5,
                            first_contact_deadline_minutes=34)["requirements"]["decision"] == "FAIL"


@pytest.mark.parametrize("states,first,contact,gap", [("BBB", None, 0, 3), ("VVV", 0, 3, 0), ("???", None, 0, 0)])
def test_empty_full_and_unknown_contact(states, first, contact, gap):
    result = analyze_contacts(payload(states))
    assert result["metrics"]["first_contact_wait_minutes"]["first_confirmed"] == first
    assert result["metrics"]["longest_contact_minutes_bounds"][0] == contact
    assert result["metrics"]["max_gap_minutes_bounds"][0] == gap
    assert result["requirements"]["decision"] is None


@pytest.mark.parametrize("validated", [False, None])
def test_validation_gate_preserves_source_decision(validated):
    data = payload("VVV")
    if validated is False:
        data["validation"]["passed"] = False
    else:
        del data["validation"]
    result = analyze_contacts(data, min_contact_minutes=3)
    assert result["requirements"]["nominal_sampled_decision"] == "PASS"
    assert result["requirements"]["decision"] == "INDETERMINATE"
    assert result["source"]["decision"] == "INDETERMINATE"


def test_all_unknown_resolutions_respect_duration_bounds():
    # Independent enumeration: missing evidence can change both joins and splits.
    for states in product("VB?", repeat=4):
        result = analyze_contacts(payload(states))["metrics"]
        indices = [i for i, s in enumerate(states) if s == "?"]
        for replacement in product("VB", repeat=len(indices)):
            resolved = list(states)
            for i, value in zip(indices, replacement):
                resolved[i] = value
            text = "".join(resolved)
            visible = max(map(len, text.split("B")))
            blocked = max(map(len, text.split("V")))
            assert result["longest_contact_minutes_bounds"][0] <= visible <= result["longest_contact_minutes_bounds"][1]
            assert result["max_gap_minutes_bounds"][0] <= blocked <= result["max_gap_minutes_bounds"][1]


@pytest.mark.parametrize("change", ["unordered", "overlap", "zero", "state", "timezone"])
def test_invalid_timeline_rejected(change):
    data = payload("VB")
    if change == "unordered":
        data["timeline"].reverse()
    elif change == "overlap":
        data["timeline"][1]["start_utc"] = data["timeline"][0]["start_utc"]
    elif change == "zero":
        data["timeline"][0]["end_utc"] = data["timeline"][0]["start_utc"]
    elif change == "state":
        data["timeline"][0]["earth_state"] = "visible"
    else:
        data["timeline"][0]["start_utc"] = "2026-11-14T00:00:00"
    with pytest.raises(ValueError):
        analyze_contacts(data)


@pytest.mark.parametrize("data", [{"points": [], "sample_stride": 12}, {"events": []}, {"sites": []}])
def test_display_timeline_and_summary_are_not_full_evidence(data):
    with pytest.raises(ValueError, match="full|timeline"):
        analyze_contacts(data)


@pytest.mark.parametrize("kwargs", [
    {"min_contact_minutes": 0}, {"min_contact_minutes": True}, {"setup_minutes": -1},
    {"max_gap_minutes": float("nan")}, {"required_windows": 1},
    {"min_contact_minutes": 1, "required_windows": True},
    {"min_contact_minutes": 1, "first_contact_deadline_minutes": 4},
    {"end_utc": (START + timedelta(days=1)).isoformat()},
])
def test_invalid_requirements_rejected(kwargs):
    with pytest.raises(ValueError):
        analyze_contacts(payload("VVV"), **kwargs)


def test_cli_json_stdin_and_csv_native_product(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/contact_windows.py"
    result = subprocess.run([sys.executable, str(script), "--input", "-", "--min-contact-minutes", "2"],
                            input=json.dumps(payload("VVV")), capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["requirements"]["decision"] == "PASS"
    output = tmp_path / "contacts.json"
    subprocess.run([sys.executable, str(script), "--input", str(root / "data/processed/lunarsight/v0.3.0/visibility/Site01_intervals.csv"),
                    "--start-utc", "2026-11-14T00:00:00Z", "--end-utc", "2026-11-17T00:00:00Z",
                    "--min-contact-minutes", "30", "--output", str(output)], check=True)
    native = json.loads(output.read_text())
    assert native["metrics"]["longest_contact_minutes_bounds"] == [675, 675]
    assert native["metrics"]["first_contact_wait_minutes"]["first_confirmed"] == 3645
    assert native["requirements"]["nominal_sampled_decision"] == "PASS"
    assert native["requirements"]["decision"] == "INDETERMINATE"  # CSV has no source validation gate.
    assert len(native["source"]["sha256"]) == 64
