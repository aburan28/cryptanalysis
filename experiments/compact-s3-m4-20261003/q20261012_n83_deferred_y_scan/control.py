#!/usr/bin/env python3
"""Independent known-base group replay for both deferred-y signs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1501-build/native_deferred_y")
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from field import Onb
from curves import Curve
from orbit_key import OrbitKey


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    onb = Onb(83)
    curve = Curve(onb)
    orbit = OrbitKey(onb)
    raw = BASE.read_bytes()
    p = orbit.point_from_key(int.from_bytes(raw[:21], "little"))
    q = orbit.point_from_key(int.from_bytes(raw[21:42], "little"))
    assert curve.onCurve(p) and curve.onCurve(q)
    controls = []
    for sign, first in ((0, p), (1, curve.neg(p))):
        target = curve.add(first, q)
        assert target is not None and curve.onCurve(target)
        args = [str(BINARY), str(BASE), format(onb.toCoords(target[0]), "x"),
                format(onb.toCoords(target[1]), "x"), "1", "1"]
        process = subprocess.run(args, text=True, capture_output=True, timeout=20)
        assert process.returncode == 0, process.stderr
        lines = process.stdout.splitlines()
        result = json.loads(lines[-1])
        assert result["hits"] >= 1 and result["scanned"] == 2
        assert any(line.startswith(f"hit 0 {sign} ") for line in lines[:-1])
        controls.append({"sign": sign, "target_x_onb_hex": args[2],
                         "target_y_onb_hex": args[3], "native_stdout": process.stdout,
                         "native_result": result})
    (HERE / "control_result.json").write_text(json.dumps({
        "proposal_id": "Q1505", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64", "isogeny": "none",
        "control_source_sha256": sha(Path(__file__)),
        "binary_sha256": sha(BINARY), "base_sha256": sha(BASE),
        "controls": controls,
        "python_group_replay": True}, indent=2, sort_keys=True) + "\n")
    print("PASS deferred-y signed base membership and replay")


if __name__ == "__main__":
    main()
