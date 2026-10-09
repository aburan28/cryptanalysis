#!/usr/bin/env python3
"""Exact two-free-pair S3 norm/gcd gate on frozen N41 output domains."""

from __future__ import annotations

import hashlib
import json
import resource
import signal
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
FIELD_RING = PolynomialRing(GF(2), "t")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def product_tree(polynomials):
    layer = list(polynomials)
    while len(layer) > 1:
        layer = [layer[i] * layer[i + 1] if i + 1 < len(layer) else layer[i]
                 for i in range(0, len(layer), 2)]
    return layer[0]


def s3(a, b, t):
    return (a * b + a * t + b * t) ** 2 + a * b * t + 1


def point(curve, field, raw):
    return curve(decode(field, raw[0]), decode(field, raw[1]))


def decode(field, value):
    return field(FIELD_RING([(int(value) >> bit) & 1 for bit in range(41)]))


def encode(value):
    return sum(int(coefficient) << bit for bit, coefficient in
               enumerate(value.polynomial().list()))


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError("preserve first run")
    started = time.monotonic_ns()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    source_paths = {
        "positive_control": (HERE / protocol["positive_control_source"]).resolve(),
        "sage_audit": (HERE / protocol["positive_control_sage_audit"]).resolve(),
        "frozen_input": (HERE / protocol["frozen_input_source"]).resolve(),
    }
    assert sha(source_paths["positive_control"]) == protocol["positive_control_sha256"]
    assert sha(source_paths["frozen_input"]) == protocol["frozen_input_sha256"]
    known = json.loads(source_paths["positive_control"].read_text())
    audit = json.loads(source_paths["sage_audit"].read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified" and audit["status"] == "PASS"
    assert known["target"] == protocol["public_target_q"]
    assert known["status"] == "VERIFIED_RAW_ROW" and len(known["row"]) == 8

    t0 = FIELD_RING.gen()
    field = GF(2**41, name="t", modulus=t0**41 + t0**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)
    q = point(curve, field, protocol["public_target_q"])
    assert 549756390943 * q == zero
    lines = source_paths["frozen_input"].read_text().splitlines()
    header = list(map(int, lines[0].split()))
    assert header == [*protocol["public_target_q"], 549756390943, 8]
    slots = []
    cursor = 1
    for _ in range(8):
        count = int(lines[cursor]); cursor += 1
        assert count == 64
        rows = [list(map(int, lines[cursor + i].split())) for i in range(count)]
        assert all(len(row) == 6 for row in rows)
        cursor += count
        slots.append(rows)
    assert cursor == len(lines)
    assert all(slots[2*i] == slots[2*i+1] for i in range(4))
    x_lists = []
    pair_counts = []
    for i in range(4):
        rows = slots[2*i]
        points = [point(curve, field, row[:2]) for row in rows]
        xs = set()
        count = 0
        for left in range(64):
            for right in range(left + 1, 64):
                if rows[left][2] == rows[right][2]:
                    continue
                total = points[left] + points[right]
                assert not total.is_zero()
                xs.add(encode(total[0]))
                count += 1
        assert count == 1956 and len(xs) == 978
        x_lists.append(sorted(xs))
        pair_counts.append(count)
    setup_ns = time.monotonic_ns() - started
    polynomial_ring = PolynomialRing(field, "Z")
    Z = polynomial_ring.gen()
    field_x = [[decode(field, x) for x in xs] for xs in x_lists]
    f3_start = time.monotonic_ns()
    f3 = product_tree((Z + b for b in field_x[3]))
    f3_ns = time.monotonic_ns() - f3_start
    assert f3.degree() == 978
    for b in field_x[3][:4]:
        assert f3(b) == 0

    row_points = [point(curve, field, entry["point"]) for entry in known["row"]]
    assert sum(row_points, zero) == q
    pair_outputs = [row_points[2*i] + row_points[2*i+1] for i in range(4)]
    assert all(not u.is_zero() for u in pair_outputs)
    assert all(encode(pair_outputs[i][0]) in x_lists[i] for i in range(4))
    positive_residual = q - pair_outputs[0] - pair_outputs[1]
    assert positive_residual == pair_outputs[2] + pair_outputs[3]
    assert s3(pair_outputs[2][0], pair_outputs[3][0], positive_residual[0]) == 0

    def lift_smallest(x):
        roots = curve.lift_x(decode(field, x), all=True)
        assert len(roots) == 2
        return min(roots, key=lambda p: encode(p[1]))

    cases = [("known_row", positive_residual)]
    for left_index, right_index in protocol["negative_prefix_pairs"]:
        u0 = lift_smallest(x_lists[0][left_index])
        u1 = lift_smallest(x_lists[1][right_index])
        cases.append((f"prefix_{left_index}_{right_index}", q - u0 - u1))

    class TimeCap(Exception):
        pass

    def alarm_handler(_signum, _frame):
        raise TimeCap()

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(protocol["limits"]["maximum_sage_job_seconds"])
    probes = []
    status = "PASS"
    try:
        for name, residual in cases:
            if residual.is_zero() or residual[0] == 0:
                raise AssertionError("exceptional residual requires separate branch")
            x_r = residual[0]
            norm_start = time.monotonic_ns()
            norm = product_tree(
                ((a + x_r)**2 * Z**2 + a*x_r*Z + (a*x_r)**2 + 1
                 for a in field_x[2]))
            norm_ns = time.monotonic_ns() - norm_start
            assert norm.degree() <= 1956
            gcd_start = time.monotonic_ns()
            common = f3.gcd(norm)
            gcd_ns = time.monotonic_ns() - gcd_start
            accepted = common.degree() > 0
            witnesses = []
            if accepted:
                for b, _multiplicity in common.roots():
                    compatible = [a for a in field_x[2] if s3(a, b, x_r) == 0]
                    for a in compatible:
                        points_a = curve.lift_x(a, all=True)
                        points_b = curve.lift_x(b, all=True)
                        if any(pa + pb == residual for pa in points_a for pb in points_b):
                            witnesses.append([encode(a), encode(b)])
            if name == "known_row":
                assert accepted and [encode(pair_outputs[2][0]), encode(pair_outputs[3][0])] in witnesses
            else:
                assert accepted == bool(witnesses)
            probes.append({
                "name": name,
                "residual": None if residual.is_zero() else [encode(residual[0]), encode(residual[1])],
                "norm_degree": int(norm.degree()),
                "gcd_degree": int(common.degree()),
                "accepted": accepted,
                "verified_group_witness_x_pairs": witnesses,
                "norm_build_ns": norm_ns,
                "gcd_ns": gcd_ns,
            })
            print(f"{name}: accepted={accepted}, norm={norm_ns/1e9:.3f}s, gcd={gcd_ns/1e9:.3f}s", flush=True)
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= protocol["limits"]["maximum_peak_rss_bytes"]:
                status = "MEMORY_GUARD"
                break
    except TimeCap:
        status = "TIME_CAP"
    finally:
        signal.alarm(0)

    report = {
        "kind": protocol["kind"],
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "status": status,
        "target": protocol["public_target_q"],
        "pair_output_x_sizes": [len(xs) for xs in x_lists],
        "pair_witness_counts": pair_counts,
        "f3_degree": int(f3.degree()),
        "input_setup_ns": setup_ns,
        "f3_build_ns": f3_ns,
        "probes": probes,
        "total_job_ns": time.monotonic_ns() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{k: sha(v) for k, v in source_paths.items()},
                          "protocol": sha(protocol_path), "run_sage": sha(Path(__file__)),
                          "sage_runtime_info": sha(HERE / "sage_runtime_info.json")},
        "claim_boundary": protocol["claim_boundary"],
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": status, "probes_completed": len(probes),
                      "total_job_seconds": report["total_job_ns"]/1e9}), flush=True)


if __name__ == "__main__":
    main()
