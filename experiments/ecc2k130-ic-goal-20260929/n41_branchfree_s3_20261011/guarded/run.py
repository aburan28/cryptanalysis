"""Frozen guarded-branch W9 control and bounded public-point query."""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "query"
PRIOR = HERE.parent.parent / "n41_transport_cubic_s8_20261011"
W9 = HERE.parent.parent / "n41_w7_entropy_cubic_20261011/w9"
spec = importlib.util.spec_from_file_location("w6_run", PRIOR / "run.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
assert Path(old.circuit.__file__).resolve() == (HERE / "circuit.py").resolve()
old_files = old.source_files()
old.HERE = RUN
old.CONSTRUCTION_CAP = 120
old.SOLVER_CAP = 120
old.PARENT_CAP = 125


def fixture():
    data = json.loads((W9 / "fixture.json").read_text())
    assert data["status"] == "W9_SOURCE_EXTENDS_VERIFIED_TRANSPORTED_PUBLIC_WITNESS"
    assert len(data["mask_columns"]) == 259
    assert len(set(data["mask_columns"].values())) == 251
    assert len(data["raw_target_reciprocals"]) == 4
    return data


def files():
    return {**{f"prior_{name}": path for name, path in old_files.items()},
            "guarded_runner": HERE / "run.py",
            "guarded_circuit": HERE / "circuit.py",
            "prior_branchfree_runner": HERE.parent / "run.py",
            "prior_branchfree_circuit": HERE.parent / "circuit.py",
            "w9_runner": W9 / "run.py",
            "w9_circuit": W9 / "circuit.py",
            "w9_geometry": W9 / "geometry.json",
            "w9_source_scan": W9 / "scan_sage.py",
            "w9_source_protocol": W9 / "protocol.json",
            "w9_fixture": W9 / "fixture.json",
            "w9_fixture_producer": W9 / "make_fixture.py",
            "w9_runtime": W9 / "sage_runtime_info.json"}


def freeze():
    f = fixture()
    assert old.SOLVER.is_file()
    record = {
        "status": "FROZEN_N41_W9_GUARDED_PUBLIC_QUERY",
        "candidate_id": None,
        "curve_id": f["curve_id"],
        "public_target_original": f["public_target_original"],
        "public_target_transported": f["public_target_transported"],
        "raw_target_preimage_z": f["raw_target_reciprocals"],
        "control_masks": f["known_masks"],
        "control_raw_preimage_index": f["known_raw_preimage_index"],
        "source_dimension": 9,
        "rotations": list(old.circuit.ROTATIONS),
        "source_rational_masks_per_window": 259,
        "factor_base_B": 2072,
        "folded_columns_K": 251,
        "workers": 1,
        "construction_cap_seconds": 120,
        "solver_cap_seconds": 120,
        "parent_solver_cap_seconds": 125,
        "rss_cap_bytes": old.RSS_CAP,
        "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                         "--random=20261011", "--maxtime=120"],
        "source_sha256": {name: old.sha(path) for name, path in files().items()},
    }
    RUN.mkdir(exist_ok=True)
    old.save(RUN / "protocol.json", record)
    print(record["status"])


def protocol():
    data = json.loads((RUN / "protocol.json").read_text())
    assert data["status"] == "FROZEN_N41_W9_GUARDED_PUBLIC_QUERY"
    assert data["source_sha256"] == {name: old.sha(path) for name, path in files().items()}
    return data


old.fixture = fixture
old.protocol = protocol


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "control", "query"):
        raise SystemExit("usage: run.py freeze|control|query")
    {"freeze": freeze, "control": old.control, "query": old.query}[sys.argv[1]]()
