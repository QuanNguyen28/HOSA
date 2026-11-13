"""Read the exact requested observer/height from validated portable products."""
import io
import json

import numpy as np
import pandas as pd

from app.core.errors import DomainError
from app.point_analysis.geometry import METHOD_VERSION, verify_profiles
from .store import Store, coordinate_key

FINE_STEP = .03125
SHORT_STEP = .0625
HEIGHTS = (1., 2., 10., 20., 30.)


def encode_profile(profile):
    stream = io.BytesIO()
    arrays = {name: profile[name].to_numpy() for name in profile.columns}
    # Object arrays are never pickled or accepted by the runtime reader.
    arrays = {name: value.astype(str) if value.dtype.kind == "O" else value for name, value in arrays.items()}
    np.savez_compressed(stream, **arrays)
    return stream.getvalue()


def decode_profile(content):
    try:
        with np.load(io.BytesIO(content), allow_pickle=False) as values:
            return pd.DataFrame({name: values[name] for name in values.files})
    except (ValueError, OSError) as error:
        raise DomainError("PRECOMPUTE_PROFILE_INVALID", 503) from error


def compatible_sources(record):
    """A newly installed source/receipt invalidates a package made with older inputs.

    With no raw DEM installed, the package is an explicitly versioned scientific
    snapshot. Its actual derived bytes and archived provenance are still checked.
    """
    from app.services.lunarsight.point import terrain_sources
    try:
        expected = {item["dataset_id"]: item["sha256"] for item in record["source_inventory"]}
    except (KeyError, TypeError) as error:
        raise DomainError("PRECOMPUTE_MANIFEST_INVALID", 503) from error
    for source in terrain_sources():
        path = source["path"]
        if not path.is_file():
            continue
        receipt = path.with_name(path.name+".receipt.json")
        try:
            metadata = json.loads(receipt.read_bytes())
            if expected.get(source["dataset_id"]) != metadata["sha256"]:
                return False
        except (OSError, ValueError, KeyError, TypeError):
            return False
    return True


class PreparedTerrain:
    def __init__(self, record, store):
        self.record, self.store = record, store
        self.site = record["site"]
        self.observer_source = record["observer_source"]

    def provenance(self):
        return self.record["datasets"]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def profiles(self, heights, step):
        fine, short = {}, {}
        for height in heights:
            for label, native_step, output in (("fine", FINE_STEP, fine), ("short", SHORT_STEP, short)):
                requested = step if label == "fine" else 2*step
                stride = int(round(requested/native_step))
                if stride < 1 or not np.isclose(stride*native_step, requested):
                    raise DomainError("PRECOMPUTE_GRID_MISMATCH", 503)
                reference = self.record["profiles"][f"{label}_h{height:g}"]
                profile = decode_profile(self.store.read(reference))
                radius = 400000 if label == "fine" else 300000
                if (len(profile) != round(360/native_step)
                        or not np.array_equal(profile.az_deg.to_numpy(), np.arange(0, 360, native_step))
                        or not (profile.height_m == height).all()
                        or not (profile.az_step_deg == native_step).all()
                        or not (profile.scan_radius_m == radius).all()):
                    raise DomainError("PRECOMPUTE_GRID_MISMATCH", 503)
                output[height] = profile.iloc[::stride].reset_index(drop=True).assign(az_step_deg=requested)
        verify_profiles(fine, self.site)
        verify_profiles(short, self.site)
        return fine, short, self.record["seams"]


def prepared_terrain(request, store=None):
    store = store or Store()
    record = store.manifest()["sites"].get(coordinate_key(request.latitude_deg, request.longitude_e_deg))
    if (not record or record.get("geometry_method") != METHOD_VERSION
            or any(height not in record["heights_m"] for height in (request.panel_height_m, request.antenna_height_m))
            or not compatible_sources(record)):
        return None
    return PreparedTerrain(record, store)
