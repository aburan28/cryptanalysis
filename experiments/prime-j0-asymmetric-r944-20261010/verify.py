#!/usr/bin/env python3
"""Bind frozen construction, inputs, atlases, native source and raw results."""

from hashlib import sha256
import gzip
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REL = HERE.relative_to(ROOT)
PROTOCOL_FREEZE = "5267db8f3"
CONSTRUCTION_FREEZE = "18f3659e6765729669a2e7cd866ae209215e6607"
INPUT_FREEZE = "185b202b1e357a6a10ae80b5d46408eab65b6d09"
MODE = "unit_orbit_u256_tau_asymmetric_radix944_gauge_xyzz_tau_fixed"


def digest(raw):
    return sha256(raw).hexdigest()


def frozen(commit, name):
    result = subprocess.run(["git", "show", f"{commit}:{REL / name}"],
                            cwd=ROOT, capture_output=True, check=True)
    return result.stdout


def check_fixture(label, fixture_path, output_bytes, expected_count):
    cases = json.loads(fixture_path.read_bytes())["cases"]
    lines = output_bytes.decode().splitlines()
    assert len(cases) == len(lines) == expected_count
    points = []
    for index, (case, line) in enumerate(zip(cases, lines)):
        assert "verified=1 " in line and f"mode={MODE}" in line, index
        scalar = line.split(" scalar=", 1)[1].split(" point=", 1)[0]
        assert scalar.lower() == case["scalar_hex"].lower(), index
        point = line.split(" point=", 1)[1].split(" mode=", 1)[0]
        expected = ("identity" if case["expected_identity"] else
                    case["expected_x_hex"] + ":" + case["expected_y_hex"])
        assert point.lower() == expected.lower(), index
        points.append(point)
    return {"cases": len(lines), "stdout_sha256": digest(output_bytes),
            "fixture_sha256": digest(fixture_path.read_bytes()),
            "point_stream_sha256": digest("\n".join(points).encode())}


def main():
    assert (HERE / "PROTOCOL.md").read_bytes() == frozen(PROTOCOL_FREEZE,
                                                       "PROTOCOL.md")
    for name in ("PROOF.md", "build_atlas.py", "verify_atlas.py",
                 "verify_group.py", "make_inputs.py", "verify_inputs.py",
                 "atlas-r944-d944.bin", "atlas-r944-d550.bin",
                 "atlas-receipt.json", "independent-check.json",
                 "design-check.json"):
        assert (HERE / name).read_bytes() == frozen(CONSTRUCTION_FREEZE, name), name
    assert (HERE / "fresh-inputs.json").read_bytes() == frozen(INPUT_FREEZE,
                                                              "fresh-inputs.json")
    subprocess.run([sys.executable, str(HERE / "verify_inputs.py")],
                   cwd=ROOT, capture_output=True, check=True)
    subprocess.run([sys.executable, str(HERE / "fast_division.py")],
                   cwd=ROOT, capture_output=True, check=True)

    atlas = json.loads((HERE / "atlas-receipt.json").read_bytes())
    independent = json.loads((HERE / "independent-check.json").read_bytes())
    group = json.loads((HERE / "group-check.json").read_bytes())
    materialization = json.loads((HERE / "native-materialization.json").read_bytes())
    native = json.loads((HERE / "native-receipt.json").read_bytes())
    assert independent["status"] == group["status"] == native["status"] == "passed"
    assert independent["verifier_sha256"] == digest((HERE / "verify_atlas.py").read_bytes())
    assert group["source_sha256"] == digest((HERE / "verify_group.py").read_bytes())
    assert group["panel"]["input_sha256"] == digest((HERE / "fresh-inputs.json").read_bytes())
    assert group["panel"]["cases"] == 4096
    assert (group["panel"]["mixed_additions"], group["panel"]["gauge_rotations"]) == (
        49_152, 14_838)
    assert atlas["point_slots"] == independent["point_slots"] == 993_953
    for bound in (944, 550):
        key = str(bound)
        binary_hash = digest((HERE / f"atlas-r944-d{bound}.bin").read_bytes())
        assert atlas["atlases"][key]["atlas_sha256"] == binary_hash
        assert independent["atlases"][key]["atlas_sha256"] == binary_hash
        assert group["atlas_sha256"][key] == binary_hash

    assert native["materializer_sha256"] == digest((HERE / "materialize_native.py").read_bytes())
    assert native["generated_sha256"] == materialization["generated_sha256"]
    assert materialization["base_patch_sha256"] == digest((HERE.parent /
        "prime-j0-mixed-radix640-20261010/native-candidate.patch").read_bytes())
    assert materialization["delta_patch_sha256"] == digest((HERE / "native-delta.patch").read_bytes())
    for key, name in (("targeted_log_sha256", "native-targeted-tests.log"),
                      ("full_log_sha256", "full-release-tests.log"),
                      ("build_log_sha256", "release-build.log")):
        assert native[key] == digest((HERE / name).read_bytes())
    targeted = (HERE / "native-targeted-tests.log").read_text()
    full = (HERE / "full-release-tests.log").read_text()
    assert "asymmetric_radix944_cases=4096 retained_bytes=71450736 additions=49152 gauge_products=14838 control_additions=53248 control_gauge_products=15105" in targeted
    assert "fast_radix944_division_cases=10595" in targeted
    assert "test result: ok. 2 passed; 0 failed;" in targeted
    assert "test result: ok. 135 passed; 0 failed;" in full

    fixtures = {
        "prior4096": (HERE.parent / "prime-j0-bound-budget15-gauge-20261010/fresh-fixture.json",
                      gzip.decompress((HERE / "prior4096.stdout.gz").read_bytes()), 4096),
        "edge": (HERE.parent / "prime-j0-tau-bucket-two-x-20261010/edge-fixture.json",
                 (HERE / "edge.stdout").read_bytes(), 10),
    }
    for label, (fixture, output, count) in fixtures.items():
        result = check_fixture(label, fixture, output, count)
        assert result == native["cli"][label]
        assert (HERE / f"{label}.stderr").read_bytes() == b""
    subprocess.run([sys.executable, str(HERE / "ops_receipt.py")],
                   cwd=ROOT, capture_output=True, check=True)
    print(json.dumps({"status": "passed", "cases": 4096,
                      "point_slots": 993_953, "retained_bytes": 71_450_736,
                      "native_binary_sha256": native["binary_sha256"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
