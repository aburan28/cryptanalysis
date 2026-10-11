"""Lift each frozen subgroup row to the raw P used in D=P+F(P)."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNTIME = HERE / "sage_runtime_info.json"
assert json.loads(RUNTIME.read_text())["status"] == "verified"
screen_path = ROOT / "n131_w18_four_pairs/screen.json"
fixture_path = ROOT / "n41_two_pair_relaxation_20261011/targets.json"
screen = json.loads(screen_path.read_text())["n41"]
fixture = json.loads(fixture_path.read_text())
assert screen["public_target_q"] == fixture["public_target_original"]

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, "t", modulus=t**41+t**3+1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])


def dec(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def halftrace(value):
    result = field.zero()
    for _ in range(21):
        result += value
        value = value**4
    return result


targets = [("positive", *fixture["known_positive"]["right_middle_point"])]
targets += [(f"control_{i}", *item["right_middle_point"])
            for i, item in enumerate(fixture["controls"])]
lines = [str(len(targets))]
lines += [f"{label} {x} {y}" for label, x, y in targets]
replays = []
for rotation in (20, 30):
    rows = screen["point_rows_by_unique_rotation"][str(rotation)]
    assert len(rows) == 64
    lines.append(f"{rotation} {len(rows)}")
    for px, py, column, mask, branch, sign in rows:
        assert branch == 0 and sign in (0, 1)
        w = dec(mask << 1)**(2**rotation)
        u = halftrace(w) + branch
        assert u not in (0, 1)
        choices = curve.lift_x(1+1/u, all=True)
        assert len(choices) == 2
        raw = choices[sign]
        subgroup = curve(dec(px), dec(py))
        assert 4*raw == subgroup
        D = raw + curve(raw[0]**2, raw[1]**2)
        assert D[0] == 1/w
        x, y = enc(raw[0]), enc(raw[1])
        lines.append(f"{x} {y} {column} {mask} {branch} {sign}")
        replays.append({"rotation": rotation, "mask": mask, "column": column,
                        "sign": sign, "raw": [x, y], "four_raw": [px, py],
                        "transported": [enc(D[0]), enc(D[1])]})
input_path = HERE / "input_v2.txt"
input_path.write_text("\n".join(lines) + "\n")
output = {"status": "PASS_SAGE_RAW_SOURCE_PREIMAGES",
          "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
          "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "runtime_sha256": hashlib.sha256(RUNTIME.read_bytes()).hexdigest(),
          "screen_sha256": hashlib.sha256(screen_path.read_bytes()).hexdigest(),
          "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
          "row_count": len(replays), "rows": replays}
(HERE / "input_v2_manifest.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
print(output["status"], "rows", len(replays))
