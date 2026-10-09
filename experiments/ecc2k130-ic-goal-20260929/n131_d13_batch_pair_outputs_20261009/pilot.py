#!/usr/bin/env sage -python
"""Bounded exact d13 pair-output pilot using the installed Sage batch adder."""

import hashlib
import json
import re
import resource
import struct
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing
from sage.schemes.elliptic_curves.binary_batch import add_pairs

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROOT = GOAL.parents[1]
CODEGEN = ROOT / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field

SOURCE = GOAL / "n131_d13_same_rotation_pairs_20261009"
GEOMETRY = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static/d13_exact_geometry_v1.json"
HEADER = ROOT / "ecc2k130/benchmarks/rtx5090-20260929/table-walk-22b-cache-build-evidence-20261004/table-walk-22b-cache-build-20261004/source/generated/eccF131.h"
RUNTIME = HERE / "sage_runtime_info.json"
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"
LEFT_COUNT = 64
WALL_CAP_SECONDS = 300
RSS_CAP_BYTES = 2 * 1024**3
R = 680564733841876926932320129493409985129


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def gamma_to_pb():
    match = re.search(r"GAMMA_TO_PB\[131\]\[3\] = \{(.*?)\n\};",
                      HEADER.read_text(), re.S)
    if not match:
        raise ValueError("missing frozen ONB to polynomial conversion")
    rows = re.findall(r"\{0x([0-9a-f]+)ull, 0x([0-9a-f]+)ull, 0x([0-9a-f]+)ull\}",
                      match.group(1))
    if len(rows) != 131:
        raise ValueError("conversion matrix row count changed")
    return [(int(a, 16) | int(b, 16) << 64 | int(c, 16) << 128)
            for a, b, c in rows]


def source_hashes():
    return {"pilot": sha(__file__), "geometry": sha(GEOMETRY),
            "valid_codes": sha(SOURCE / "valid_codes.json"),
            "onb_field": sha(CODEGEN / "field.py"),
            "onb_curve": sha(CODEGEN / "curves.py"),
            "conversion_header": sha(HEADER), "runtime": sha(RUNTIME)}


def freeze():
    if PROTOCOL.exists():
        raise FileExistsError("preserve frozen pilot protocol")
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    valid = json.loads((SOURCE / "valid_codes.json").read_text())
    assert len(valid) == 4134 and valid == sorted(set(valid))
    geometry = json.loads(GEOMETRY.read_text())
    assert geometry["domain"]["dimension"] == 13
    payload = {"kind": "n131_d13_batch_pair_output_pilot",
               "curve_id": "EC1N131Ckb1h136f03e58c98",
               "left_count": LEFT_COUNT, "valid_code_count": len(valid),
               "field_modulus_exponents": [0, 1, 2, 13, 131],
               "source_sha256": source_hashes(),
               "wall_cap_seconds": WALL_CAP_SECONDS,
               "rss_cap_bytes": RSS_CAP_BYTES,
               "record_bytes": 21, "candidate_id": None, "run_id": None}
    PROTOCOL.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "left_count": LEFT_COUNT}))


def setup():
    protocol = json.loads(PROTOCOL.read_text())
    if protocol["source_sha256"] != source_hashes():
        raise ValueError("frozen source or checked runtime changed")
    geometry = json.loads(GEOMETRY.read_text())
    basis = [int(mask, 16) for mask in
             geometry["domain"]["basis_coordinate_masks_hex"]]
    valid = json.loads((SOURCE / "valid_codes.json").read_text())
    gamma = gamma_to_pb()
    onb = field.Onb(131)
    raw_curve = curves.Curve(onb)
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    k = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(k, [1, 0, 0, 0, 1])

    def to_pb(value):
        bits = onb.toCoords(value)
        image = 0
        while bits:
            lowest = bits & -bits
            image ^= gamma[lowest.bit_length()-1]
            bits ^= lowest
        return image

    def to_sage(value):
        bits = to_pb(value)
        return k(ring([(bits >> i) & 1 for i in range(131)]))

    def sage_int(value):
        return sum(int(coefficient) << i for i, coefficient in
                   enumerate(value.polynomial().list()))

    assert to_pb(onb.one()) == 1
    points = []
    raw_points = []
    for code in valid:
        coordinate = 0
        for bit, value in enumerate(basis):
            if code & (1 << bit):
                coordinate ^= value
        phi = onb.fromCoords(coordinate)
        raw = raw_curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
        if raw is None or raw_curve.mul(raw, 4) is None:
            raise ValueError("frozen usable code failed independent lift")
        sage_point = curve(to_sage(raw[0]), to_sage(raw[1]))
        if 4 * sage_point == curve(0) or R * (4 * sage_point) != curve(0):
            raise ValueError("converted point failed subgroup check")
        points.append(sage_point)
        raw_points.append(raw)
    return protocol, onb, raw_curve, curve, valid, points, raw_points, to_pb, sage_int


def run():
    if RESULT.exists():
        raise FileExistsError("preserve first batch-output result")
    start = time.monotonic_ns()
    (protocol, onb, raw_curve, curve, valid, points, raw_points,
     to_pb, sage_int) = setup()
    setup_ns = time.monotonic_ns() - start
    hash_rows = hashlib.sha256()
    seen = set()
    samples = []
    pairs = 0
    outputs = 0
    exceptional = 0
    batch_ns = 0
    encode_ns = 0
    for left_index in range(protocol["left_count"]):
        partners = list(range(left_index + 1, len(valid)))
        p = points[left_index]
        t0 = time.monotonic_ns()
        plus = add_pairs(curve, [(p, points[j]) for j in partners])
        minus = add_pairs(curve, [(p, -points[j]) for j in partners])
        batch_ns += time.monotonic_ns() - t0
        t0 = time.monotonic_ns()
        for j, plus_point, minus_point in zip(partners, plus, minus):
            pairs += 1
            for branch, value in enumerate((plus_point, minus_point)):
                if value == curve(0):
                    raise ValueError("distinct valid codes produced identity")
                x = sage_int(value[0])
                hash_rows.update(x.to_bytes(17, "little"))
                hash_rows.update(struct.pack("<HH", valid[left_index], valid[j]))
                hash_rows.update(bytes((branch,)))
                seen.add(x)
                outputs += 1
                exceptional += int(value[0] == 1)
                if len(samples) < 32 or outputs % 8191 == 0 and len(samples) < 96:
                    samples.append({"left_code": valid[left_index],
                                    "right_code": valid[j], "branch": branch,
                                    "x_pb": x})
        encode_ns += time.monotonic_ns() - t0
        if ((time.monotonic_ns() - start) / 1e9 > protocol["wall_cap_seconds"] or
                peak_rss() > protocol["rss_cap_bytes"]):
            failure = {"status": "CENSORED_CAP", "completed_left": left_index+1,
                       "elapsed_ns": time.monotonic_ns()-start,
                       "peak_rss_bytes": peak_rss(), "protocol_sha256": sha(PROTOCOL)}
            (HERE / "failure.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n")
            raise RuntimeError("frozen pair-output pilot cap")
    result = {"kind": "n131_d13_batch_pair_output_pilot",
              "status": "PASS", "curve_id": protocol["curve_id"],
              "left_count": protocol["left_count"],
              "unordered_pairs": pairs, "signed_x_outputs": outputs,
              "distinct_output_x": len(seen), "x_one_outputs": exceptional,
              "output_stream_sha256": hash_rows.hexdigest(),
              "samples": samples, "setup_ns": setup_ns,
              "batch_add_ns": batch_ns, "encode_ns": encode_ns,
              "elapsed_ns": time.monotonic_ns()-start,
              "peak_rss_bytes": peak_rss(),
              "full_domain_unordered_pairs": len(valid)*(len(valid)-1)//2,
              "full_domain_signed_outputs_upper": len(valid)*(len(valid)-1),
              "full_domain_raw_payload_bytes_upper":
                  len(valid)*(len(valid)-1)*protocol["record_bytes"],
              "protocol_sha256": sha(PROTOCOL)}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "unordered_pairs", "signed_x_outputs",
                       "distinct_output_x", "elapsed_ns", "peak_rss_bytes")}))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "run"):
        raise SystemExit("usage: pilot.py freeze|run")
    freeze() if sys.argv[1] == "freeze" else run()
