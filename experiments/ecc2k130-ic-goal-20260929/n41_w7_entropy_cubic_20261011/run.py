"""Frozen W7 public-point circuit control and bounded unpinned query."""

import importlib.util
import json
import sys
from pathlib import Path


HERE=Path(__file__).resolve().parent
RUN=HERE/"query"
PRIOR=HERE.parent/"n41_transport_cubic_s8_20261011"
spec=importlib.util.spec_from_file_location("w6_run",PRIOR/"run.py")
old=importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
assert Path(old.circuit.__file__).resolve()==(HERE/"circuit.py").resolve()
old_files=old.source_files()
old.HERE=RUN
old.CONSTRUCTION_CAP=120
old.SOLVER_CAP=120
old.PARENT_CAP=125


def fixture():
    data=json.loads((HERE/"fixture.json").read_text())
    assert data["status"]=="W7_SOURCE_EXTENDS_VERIFIED_TRANSPORTED_PUBLIC_WITNESS"
    assert len(data["mask_columns"])==63
    assert len(set(data["mask_columns"].values()))==57
    assert len(data["raw_target_reciprocals"])==4
    return data


def files():
    return {**{f"prior_{name}":path for name,path in old_files.items()},
            "w7_runner":HERE/"run.py","w7_circuit":HERE/"circuit.py",
            "w7_geometry":HERE/"geometry.json","w7_scan":HERE/"scan_sage.py",
            "w7_scan_protocol":HERE/"protocol.json",
            "w7_fixture":HERE/"fixture.json",
            "w7_fixture_producer":HERE/"make_fixture.py",
            "w7_runtime":HERE/"sage_runtime_info.json"}


def freeze():
    f=fixture()
    assert old.SOLVER.is_file()
    record={"status":"FROZEN_N41_W7_PUBLIC_CUBIC_QUERY",
            "candidate_id":None,"curve_id":f["curve_id"],
            "public_target_original":f["public_target_original"],
            "public_target_transported":f["public_target_transported"],
            "raw_target_preimage_z":f["raw_target_reciprocals"],
            "control_masks":f["known_masks"],
            "control_raw_preimage_index":f["known_raw_preimage_index"],
            "source_dimension":7,"rotations":list(old.circuit.ROTATIONS),
            "source_rational_masks_per_window":63,
            "factor_base_B":504,"folded_columns_K":57,
            "workers":1,"construction_cap_seconds":120,
            "solver_cap_seconds":120,"parent_solver_cap_seconds":125,
            "rss_cap_bytes":old.RSS_CAP,
            "solver_flags":["--threads=1","--xor=0","--printsol=1",
                            "--random=20261011","--maxtime=120"],
            "source_sha256":{name:old.sha(path) for name,path in files().items()}}
    RUN.mkdir(exist_ok=True)
    old.save(RUN/"protocol.json",record)
    print(record["status"])


def protocol():
    data=json.loads((RUN/"protocol.json").read_text())
    assert data["status"]=="FROZEN_N41_W7_PUBLIC_CUBIC_QUERY"
    assert data["source_sha256"]=={name:old.sha(path) for name,path in files().items()}
    return data


old.fixture=fixture
old.protocol=protocol


if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in ("freeze","control","query"):
        raise SystemExit("usage: run.py freeze|control|query")
    {"freeze":freeze,"control":old.control,"query":old.query}[sys.argv[1]]()
