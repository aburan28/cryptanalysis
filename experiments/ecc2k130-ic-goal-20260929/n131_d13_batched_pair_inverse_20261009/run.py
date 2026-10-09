#!/usr/bin/env sage -python
"""Compare exact all-sum d13 pair inverse with linear batched RHS generation."""

import hashlib
import json
import resource
import statistics
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import field

N, DIM, DOMAIN = 131, 13, 8192
HEADER = struct.Struct("<8sHBB")
METHODS = ("direct_product", "linear_dense", "linear_gray")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def read_index(path):
    rows = []
    with path.open("rb") as stream:
        if HEADER.unpack(stream.read(HEADER.size)) != (b"D13PIV1\0", DOMAIN, N, DIM):
            raise ValueError("source index header changed")
        for s in range(DOMAIN):
            width = stream.read(1)
            if len(width) != 1 or width[0] != (0 if s == 0 else 12):
                raise ValueError("source index rank changed")
            group = []
            for _ in range(width[0]):
                data = stream.read(20)
                if len(data) != 20:
                    raise ValueError("truncated source index")
                group.append((data[0], int.from_bytes(data[1:18], "little"),
                              int.from_bytes(data[18:20], "little")))
            rows.append(group)
        if stream.read(1):
            raise ValueError("trailing source index bytes")
    return rows


def solve_rows(rows, rhs):
    code = 0
    for leading, pivot, combo in rows:
        if (rhs >> leading) & 1:
            rhs ^= pivot
            code ^= combo
    return code if rhs == 0 else None


def add_pair(found, code, s, valid):
    if code is not None:
        partner = code ^ s
        if code != partner and code in valid and partner in valid:
            found.add(tuple(sorted((code, partner))))


def direct_product(onb, rows, valid, seed_squares, z_mask):
    z = onb.fromCoords(z_mask)
    denominator = onb.add(onb.sqr(z), z)
    if denominator == 0:
        return []
    reciprocal = onb.inv(denominator)
    offset = onb.sqr(z)
    found = set()
    for s in range(1, DOMAIN):
        rhs = onb.mul(onb.add(seed_squares[s], offset), reciprocal)
        add_pair(found, solve_rows(rows[s], onb.toCoords(rhs)), s, valid)
    return sorted(found)


def linear_terms(onb, squared_basis, z_mask):
    z = onb.fromCoords(z_mask)
    denominator = onb.add(onb.sqr(z), z)
    if denominator == 0:
        return None
    reciprocal = onb.inv(denominator)
    return (onb.mul(onb.sqr(z), reciprocal),
            [onb.mul(value, reciprocal) for value in squared_basis])


def linear_dense(onb, rows, valid, squared_basis, z_mask):
    terms = linear_terms(onb, squared_basis, z_mask)
    if terms is None:
        return []
    offset, columns = terms
    rhs_by_sum = [0] * DOMAIN
    rhs_by_sum[0] = offset
    found = set()
    for s in range(1, DOMAIN):
        low = s & -s
        rhs = rhs_by_sum[s ^ low] ^ columns[low.bit_length() - 1]
        rhs_by_sum[s] = rhs
        add_pair(found, solve_rows(rows[s], onb.toCoords(rhs)), s, valid)
    return sorted(found)


def linear_gray(onb, rows, valid, squared_basis, z_mask):
    terms = linear_terms(onb, squared_basis, z_mask)
    if terms is None:
        return []
    rhs, columns = terms
    found = set()
    for step in range(1, DOMAIN):
        low = step & -step
        rhs ^= columns[low.bit_length() - 1]
        s = step ^ (step >> 1)
        add_pair(found, solve_rows(rows[s], onb.toCoords(rhs)), s, valid)
    return sorted(found)


def summary(values):
    deciles = statistics.quantiles(values, n=10, method="inclusive")
    return {"count": len(values), "median_ns": int(statistics.median(values)),
            "min_ns": min(values), "max_ns": max(values),
            "p10_ns": int(deciles[0]), "p90_ns": int(deciles[-1]),
            "mean_ns": int(statistics.mean(values))}


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    expected = protocol["source_sha256"]
    paths = {"run": HERE / "run.py", "field": CODEGEN / "field.py",
             "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "source_result": SOURCE / "result.json",
             "runtime": HERE / "runtime_info.json"}
    if (protocol["status"] != "FROZEN" or
            any(sha(path) != expected[name] for name, path in paths.items()) or
            json.loads(paths["runtime"].read_text())["status"] != "verified"):
        raise ValueError("frozen source or checked Sage runtime changed")
    rows = read_index(paths["pivots"])
    valid = set(json.loads(paths["valid_codes"].read_text()))
    if len(valid) != 4134:
        raise ValueError("source selector count changed")
    onb = field.Onb(N)
    basis = [onb.fromCoords(int(mask, 16)) for mask in protocol["basis_masks_hex"]]
    squared_basis = [onb.sqr(value) for value in basis]
    seed_squares = [0] * DOMAIN
    for s in range(1, DOMAIN):
        low = s & -s
        seed_squares[s] = seed_squares[s ^ low] ^ squared_basis[low.bit_length() - 1]
    inputs = protocol["inputs"]
    if (len(basis) != DIM or len(inputs) != 64 or
            len({item["z_mask"] for item in inputs}) != len(inputs) or
            protocol["repetitions"] != 2):
        raise ValueError("frozen input shape changed")
    source = json.loads(paths["source_result"].read_text())
    if any(item["z_mask"] != source["positive_controls"][i]["output_phi_mask"]
           for i, item in enumerate(inputs[:32])):
        raise ValueError("positive controls changed")
    operations = {"direct_product": lambda z: direct_product(onb, rows, valid,
                                                              seed_squares, z),
                  "linear_dense": lambda z: linear_dense(onb, rows, valid,
                                                          squared_basis, z),
                  "linear_gray": lambda z: linear_gray(onb, rows, valid,
                                                        squared_basis, z)}
    warm = inputs[0]["z_mask"]
    reference = operations["direct_product"](warm)
    if any(operations[name](warm) != reference for name in METHODS[1:]):
        raise ValueError("warm-up methods disagree")
    start = time.monotonic_ns()
    raw = []
    pair_results = []
    for repetition in range(protocol["repetitions"]):
        for i, item in enumerate(inputs):
            z_mask = item["z_mask"]
            order = METHODS[(i + repetition) % 3:] + METHODS[:(i + repetition) % 3]
            outputs = {}
            for name in order:
                t0 = time.monotonic_ns()
                outputs[name] = operations[name](z_mask)
                duration = time.monotonic_ns() - t0
                raw.append({"repetition": repetition, "input_index": i,
                            "method": name, "wall_ns": duration,
                            "pair_count": len(outputs[name])})
            if outputs["direct_product"] != outputs["linear_dense"] or \
                    outputs["direct_product"] != outputs["linear_gray"]:
                raise ValueError(f"method disagreement on input {i}")
            if item["kind"] == "positive" and tuple(item["pair"]) not in outputs["direct_product"]:
                raise ValueError(f"positive pair missing on input {i}")
            if repetition == 0:
                pair_results.append({"input_index": i, "z_mask": z_mask,
                                     "kind": item["kind"],
                                     "pairs": [list(pair) for pair in outputs["direct_product"]]})
            if (time.monotonic_ns() - start >
                    protocol["wall_cap_seconds"] * 1_000_000_000 or
                    rss_bytes() > protocol["rss_cap_bytes"]):
                raise RuntimeError("frozen time or process RSS cap reached")
    groups = {name: [row["wall_ns"] for row in raw if row["method"] == name]
              for name in METHODS}
    by_key = {(row["repetition"], row["input_index"], row["method"]): row["wall_ns"]
              for row in raw}
    paired = {name: [by_key[(rep, i, "direct_product")] /
                     by_key[(rep, i, name)]
                     for rep in range(protocol["repetitions"]) for i in range(len(inputs))]
              for name in METHODS[1:]}
    receipt = {"kind": "n131_d13_batched_exact_pair_inverse", "status": "PASS_EXACT_MATCH",
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "run_id": None, "curve_id": protocol["curve_id"],
               "method_order": list(METHODS), "input_count": len(inputs),
               "positive_count": 32, "control_count": 32,
               "repetitions": protocol["repetitions"],
               "complete_sum_count_per_input": DOMAIN - 1,
               "field_products_per_input": {"direct_product": DOMAIN - 1,
                                            "linear_dense": DIM + 1,
                                            "linear_gray": DIM + 1},
               "input_pair_results": pair_results, "raw": raw,
               "method_wall_ns": {name: summary(values) for name, values in groups.items()},
               "paired_direct_over_linear":
               {name: {"median": statistics.median(values),
                       "p10": statistics.quantiles(values, n=10, method="inclusive")[0],
                       "p90": statistics.quantiles(values, n=10, method="inclusive")[-1],
                       "min": min(values), "max": max(values)}
                for name, values in paired.items()},
               "measurement_wall_ns": time.monotonic_ns() - start,
               "peak_process_rss_bytes": rss_bytes(),
               "source_sha256": {"protocol": sha(protocol_path),
                                 **{name: sha(path) for name, path in paths.items()}}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "method_wall_ns": receipt["method_wall_ns"],
                      "paired_direct_over_linear": receipt["paired_direct_over_linear"]}))


if __name__ == "__main__":
    main()
