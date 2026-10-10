#!/usr/bin/env python3
"""Independently parse and replay the frozen native W15 norm certificate."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "n131_w15_pair_bucket_polynomial_20261010"
MODULUS = (1 << 131) | (1 << 13) | 7
MASK = (1 << 131) - 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a, b):
    result = 0
    while a:
        if a & 1:
            result ^= b
        a >>= 1
        b <<= 1
        if b & (1 << 131):
            b ^= MODULUS
    return result


def evaluate(terms, value):
    powers = [value]
    for _ in range(15):
        powers.append(mul(powers[-1], powers[-1]))
    result = 0
    for exponent, coefficient in terms:
        term = coefficient
        k = 0
        while exponent:
            if exponent & 1:
                term = mul(term, powers[k])
            exponent >>= 1
            k += 1
        result ^= term
    return result


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    run = json.loads((HERE / "result.json").read_text())
    freeze = json.loads((HERE / "audit_protocol.json").read_text())
    assert freeze["status"] == "FROZEN_BEFORE_INDEPENDENT_AUDIT"
    for rel, wanted in freeze["sha256"].items():
        assert sha((HERE / rel).resolve()) == wanted, rel
    assert run["status"] == "COMPLETE" and run["returncode"] == 0
    assert run["protocol_sha256"] == sha(HERE / "protocol.json")
    assert run["coefficients_sha256"] == sha(HERE / "coefficients.tsv")
    assert protocol["seed"] == 13686
    assert run["native_reported_peak_rss_bytes"] < protocol["rss_cap_bytes"]
    old = json.loads((ARCHIVE / "polynomial_sparse_v3.json").read_text())
    old_result = json.loads((ARCHIVE / "result_v3.json").read_text())
    terms = []
    for line in (HERE / "coefficients.tsv").read_text().splitlines():
        exponent, lo, mid, hi = map(int, line.split("\t"))
        coefficient = lo | (mid << 64) | (hi << 128)
        assert 0 < coefficient <= MASK
        terms.append((exponent, coefficient))
    assert terms == [tuple(row) for row in old["terms"]]
    assert len(terms) == 486 and terms[-1][0] == 32768
    digest = hashlib.sha256()
    coefficient_map = dict(terms)
    for exponent in range(32769):
        digest.update(coefficient_map.get(exponent, 0).to_bytes(17, "little"))
    assert digest.hexdigest() == old["dense_coefficient_sha256"]
    assert digest.hexdigest() == old_result["n131"]["coefficient_sha256"]
    positive = old_result["n131"]["known_normalized_pair_output"]
    evaluations = [evaluate(terms, x) for x in [positive, 3, 7]]
    assert evaluations[0] == 0
    assert evaluations[1] != 0 and evaluations[2] != 0
    report = {"status": "PASS_INDEPENDENT_NATIVE_NORM_REPLAY",
              "degree": terms[-1][0], "nonzero_coefficients": len(terms),
              "dense_coefficient_sha256": digest.hexdigest(),
              "all_sparse_coefficients_match_archive": True,
              "independent_evaluations": evaluations,
              "native_reported_peak_rss_bytes": run["native_reported_peak_rss_bytes"],
              "native_elapsed_ns": int(float((HERE / "run.stdout.txt").read_text().split("elapsed_s=")[-1].split()[0])*1e9),
              "parent_wall_ns": run["parent_wall_ns"],
              "audit_protocol_sha256": sha(HERE / "audit_protocol.json"),
              "candidate_id": None, "target_count": 0}
    with (HERE / "audit_result.json").open("x") as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
