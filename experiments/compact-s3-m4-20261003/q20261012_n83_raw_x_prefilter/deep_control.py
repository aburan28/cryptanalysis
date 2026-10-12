#!/usr/bin/env python3
"""Check both signs and a noninitial Frobenius orbit in the exact Bloom scan."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1512-native-prefilter")
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from curves import Curve  # noqa: E402
from field import Onb  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / "deep_control.json"
    assert not out.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert sha(BASE) == protocol["base_point_file_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    onb = Onb(83)
    curve = Curve(onb)
    orbit = OrbitKey(onb)
    raw = BASE.read_bytes()
    def representative(index):
        return orbit.point_from_key(int.from_bytes(raw[index * 21:(index + 1) * 21], "little"))
    orbit_index, shift = 142, 37
    position = orbit_index * 83 + shift
    p = curve.frob(representative(orbit_index), shift)
    q = curve.frob(representative(3), 19)
    assert curve.onCurve(p) and curve.onCurve(q)
    rows = []
    for sign in (0, 1):
        first = curve.neg(p) if sign else p
        target = curve.add(first, q)
        assert target is not None and curve.onCurve(target)
        x, y = [format(onb.toCoords(v), "x") for v in target]
        for bits, hashes in ((0, 0), (28, 4)):
            args = [str(BINARY), str(BASE), x, y, str(position + 1), "512",
                    str(bits), str(hashes)]
            process = subprocess.run(args, text=True, capture_output=True, timeout=30)
            assert process.returncode == 0, process.stderr
            lines = process.stdout.splitlines()
            native = json.loads(lines[-1])
            assert native["hits"] >= 1
            assert any(line.startswith(f"hit {position} {sign} ") for line in lines[:-1])
            rows.append({"sign": sign, "mode": [bits, hashes],
                         "target_onb_xy_hex": [x, y],
                         "native": native, "stdout": process.stdout})
    for sign in (0, 1):
        baseline, bloom = [r for r in rows if r["sign"] == sign]
        assert baseline["native"]["raw_x_checksum_hex"] == bloom["native"]["raw_x_checksum_hex"]
        assert baseline["native"]["hits"] == bloom["native"]["hits"]
    out.write_text(json.dumps({"proposal_id": "Q1512", "curve_id": protocol["curve_id"],
                               "isogeny": "none", "base_sha256": sha(BASE),
                               "binary_sha256": sha(BINARY),
                               "source_sha256": sha(Path(__file__)),
                               "orbit_index": orbit_index, "frobenius_shift": shift,
                               "base_scan_position": position,
                               "rows": rows}, indent=2, sort_keys=True) + "\n")
    print("PASS Q1512 deep-orbit signed controls", position)


if __name__ == "__main__":
    main()
