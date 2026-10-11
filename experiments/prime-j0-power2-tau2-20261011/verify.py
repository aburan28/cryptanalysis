#!/usr/bin/env python3
"""Bind frozen three-image construction to paired group and native receipts."""

from hashlib import sha256
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REL = HERE.relative_to(ROOT)
PARENT = HERE.parent / "prime-j0-power2-residual-20261010"
CONSTRUCTION = "10ca081d3469a392f78a6069b49839aeaf375e16"
INPUT_LAW = "edcd1214148e68305d719c0c53ee6da1ce8a002f"
PANEL = "c705ac1c21c02eec51cc18cf52c046d0090c7193"


def digest(raw):
    return sha256(raw).hexdigest()


def read_json(name):
    return json.loads((HERE / name).read_bytes())


def frozen(commit, name):
    return subprocess.check_output(["git", "show", f"{commit}:{REL / name}"],
                                   cwd=ROOT)


def main():
    for name in ("PROTOCOL.md", "PROOF.md", "build_atlas.py", "verify_atlas.py",
                 "atlas-r1024-full-tau2.bin", "atlas-r1024-terminal-tau2.bin",
                 "atlas-receipt.json", "independent-check.json"):
        assert (HERE / name).read_bytes() == frozen(CONSTRUCTION, name), name
    for name in ("make_inputs.py", "verify_inputs.py"):
        assert (HERE / name).read_bytes() == frozen(INPUT_LAW, name), name
    assert (HERE / "fresh-inputs.json").read_bytes() == frozen(
        PANEL, "fresh-inputs.json")
    subprocess.run([sys.executable, str(HERE / "verify_inputs.py")],
                   cwd=ROOT, check=True, capture_output=True)
    subprocess.run([sys.executable, str(HERE / "verify_atlas.py")],
                   cwd=ROOT, check=True, capture_output=True)

    atlas = read_json("atlas-receipt.json")
    independent = read_json("independent-check.json")
    group = read_json("group-check.json")
    design = read_json("design-check.json")
    control = read_json("control-group.json")
    native = read_json("native-targeted.json")
    edge = read_json("native-edge-check.json")
    host = read_json("host-cache-observation.json")
    assert atlas["affine_slots"] == 890_292
    assert independent["status"] == group["status"] == design["status"] == \
           control["status"] == native["status"] == edge["status"] == "passed"
    assert independent["verifier_sha256"] == digest((HERE / "verify_atlas.py").read_bytes())
    assert group["source_sha256"] == design["source_sha256"] == digest(
        (HERE / "verify_group.py").read_bytes())
    panel_hash = digest((HERE / "fresh-inputs.json").read_bytes())
    assert group["panel"]["input_sha256"] == control["control"]["input_sha256"] \
           == panel_hash
    assert group["panel"] == control["candidate"]
    assert group["panel"]["output_sha256"] == control["control"]["output_sha256"]
    assert (group["panel"]["cases"], group["panel"]["mixed_additions"],
            group["panel"]["gauge_rotations"], group["panel"]["outer_tau_images"]) == (
                4096, 49_151, 18_186, 7_734)
    assert (control["control"]["mixed_additions"],
            control["control"]["gauge_rotations"]) == (49_151, 14_882)
    assert control["candidate_source_sha256"] == group["source_sha256"]
    assert control["control_source_sha256"] == digest(
        (PARENT / "verify_group.py").read_bytes())
    for name, path in (("full", "atlas-r1024-full-tau2.bin"),
                       ("terminal", "atlas-r1024-terminal-tau2.bin")):
        expected = digest((HERE / path).read_bytes())
        assert atlas[name]["atlas_sha256"] == independent[name]["atlas_sha256"] \
               == group["atlas_sha256"][name] == expected

    assert native["native_delta_sha256"] == digest((HERE / "native-delta.patch").read_bytes())
    assert native["assets_sha256"]["fresh-inputs.json"] == panel_hash
    with tempfile.TemporaryDirectory(prefix="power2-tau2-verify-") as temp:
        output = Path(temp) / "native"
        subprocess.run([sys.executable, str(HERE / "materialize_native.py"),
                        str(output)], cwd=ROOT, check=True, capture_output=True)
        materialized = json.loads((output / "materialization.json").read_text())
        assert native["generated_sha256"] == materialized["generated_sha256"]
        assert native["assets_sha256"] == materialized["assets_sha256"]
        assert native["native_delta_sha256"] == materialized["native_delta_sha256"]

    compressed = (HERE / "native-targeted-tests.log.gz").read_bytes()
    raw = gzip.decompress(compressed)
    assert native["compressed_log_sha256"] == digest(compressed)
    assert native["raw_log_sha256"] == digest(raw)
    assert b"test result: ok. 1 passed; 0 failed;" in raw
    assert (native["cases"], native["retained_bytes"],
            native["mixed_additions"], native["gauge_rotations"],
            native["control_mixed_additions"],
            native["control_gauge_rotations"]) == (
                4096, 61_829_108, 49_151, 18_186, 49_151, 14_882)

    sys.path.insert(0, str(PARENT))
    from verify_fixture import check_fixture
    checker_hash = digest((PARENT / "verify_fixture.py").read_bytes())
    assert edge["checker_sha256"] == checker_hash
    edge_compressed = (HERE / "native-edge.stdout.gz").read_bytes()
    assert edge["compressed_stdout_sha256"] == digest(edge_compressed)
    fixture = HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json"
    edge_result = check_fixture(edge["mode"], "edge", fixture,
                                gzip.decompress(edge_compressed), 10)
    assert all(edge[key] == value for key, value in edge_result.items())
    assert edge["raw_stderr_bytes"] == 0

    assert host["l3_cache_reported"] == "64 MiB"
    assert host["scope"] == "container_visible_lscpu_not_host_isolation"
    l3_bytes = 64 * 1024 * 1024
    assert native["retained_bytes"] < l3_bytes < 72_663_424
    print(json.dumps({"status": "passed", "cases": 4096,
                      "affine_slots": atlas["affine_slots"],
                      "retained_bytes": native["retained_bytes"],
                      "cache_boundary_bytes": l3_bytes}, sort_keys=True))


if __name__ == "__main__":
    main()
