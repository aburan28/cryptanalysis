#!/usr/bin/env sage -python
"""Derive complete rotated pair-output roots and minimal absent prefixes."""

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import psutil
from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
CONTROL = BASE / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def batch_inverse(values, field):
    assert all(value != 0 for value in values)
    prefix = []
    product = field.one()
    for value in values:
        prefix.append(product)
        product *= value
    inverse = 1 / product
    result = {}
    for value, head in zip(reversed(values), reversed(prefix)):
        result[value] = inverse * head
        inverse *= value
    assert inverse == 1
    return result


def halftrace(value, field):
    result = field.zero()
    power = value
    for _ in range(66):
        result += power
        power = power**4
    return result if result*result + result == value else None


def forbidden_prefixes(allowed, bits):
    by_depth = [{0}]
    for depth in range(1, bits+1):
        by_depth.append({value & ((1 << depth)-1) for value in allowed})
    missing = []
    for depth in range(bits):
        for prefix in sorted(by_depth[depth]):
            for bit in (0, 1):
                child = prefix | (bit << depth)
                if child not in by_depth[depth+1]:
                    missing.append([depth+1, child])
    return missing


def main():
    started = time.monotonic()
    protocol = json.loads((HERE / "projection_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_W15_PAIR_OUTPUT_PREFIX_PRODUCER"
    from freeze import sources
    assert protocol["source_sha256"] == {name: sha(path)
                                          for name, path in sources().items()}
    assert not (HERE / "pair_roots.json").exists()
    assert not (HERE / "prefix_table.json").exists()
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss

    def resource_check():
        nonlocal peak_rss
        peak_rss = max(peak_rss, parent.memory_info().rss)
        assert time.monotonic()-started < protocol["producer_wall_cap_seconds"]
        assert peak_rss < protocol["rss_cap_bytes"]

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    basis = [field.gen()**(i+1) for i in range(15)]
    values = [field.zero()] * (1 << 15)
    for mask in range(1, 1 << 15):
        low = mask & -mask
        values[mask] = values[mask ^ low] + basis[low.bit_length()-1]
    assert all(encode(values[1 << i]) == 1 << (i+1) for i in range(15))
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    assert len(columns) == protocol["source_masks"]
    control = json.loads(CONTROL.read_text())
    rows_by_seed = []
    tables = []
    for index, (seed_code, rotation) in enumerate(zip(protocol["seeds"],
                                                       protocol["rotations"])):
        seed = values[seed_code]
        raw_pairs = [(mask, mask ^ seed_code)
                     for mask, column in columns.items()
                     if (mask ^ seed_code) in columns and mask < (mask ^ seed_code)
                     and column != columns[mask ^ seed_code]]
        products = [values[a] * values[b] for a, b in raw_pairs]
        assert len(set(products)) == len(products)
        assert all(p != 0 and p != 1 for p in products)
        inverses = batch_inverse(list({value for p in products
                                       for value in (p, 1+p)}), field)
        rows = []
        output_set = set()
        for pair_index, ((a, b), p) in enumerate(zip(raw_pairs, products)):
            if pair_index % 128 == 0:
                resource_check()
            one_plus = 1+p
            rhs = (one_plus*one_plus) * (seed*seed) * (inverses[p]**2)
            h = halftrace(rhs, field)
            assert h is not None
            scale = p * (inverses[one_plus]**2)
            roots = [scale*h, scale*(h+1)]
            assert roots[0] != roots[1]
            for root in roots:
                assert (1+p*p)*root*root + p*root + seed*seed == 0
                for _ in range(rotation):
                    root = root*root
                output_set.add(encode(root))
            rotated = []
            for root in roots:
                for _ in range(rotation):
                    root = root*root
                rotated.append(encode(root))
            rows.append([a, b, *sorted(rotated)])
        control_masks = control["masks"][2*index:2*index+2]
        control_reciprocal = control["middle_reciprocals"][index]
        assert any(set(row[:2]) == set(control_masks) and
                   control_reciprocal in row[2:] for row in rows)
        allowed = sorted({value & 0xffff for value in output_set})
        forbidden = forbidden_prefixes(allowed, protocol["prefix_bits"])
        assert 0 < len(allowed) < (1 << protocol["prefix_bits"])
        rows_by_seed.append({"seed": seed_code, "rotation": rotation,
                             "pairs": rows})
        tables.append({"seed": seed_code, "rotation": rotation,
                       "allowed_prefixes": allowed,
                       "forbidden_prefixes": forbidden,
                       "unordered_pair_count": len(rows),
                       "distinct_full_outputs": len(output_set)})
        print(json.dumps({"pair": index, "mask_pairs": len(rows),
                          "full_outputs": len(output_set),
                          "allowed_prefixes": len(allowed),
                          "forbidden_clauses": len(forbidden)}), flush=True)
    resource_check()
    root_receipt = {"status": "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS",
                    "curve_id": protocol["curve_id"],
                    "target_count": 0, "prefix_bits": protocol["prefix_bits"],
                    "pair_rows": rows_by_seed,
                    "sha256": {"producer": sha(Path(__file__)),
                               "protocol": sha(HERE / "projection_protocol.json"),
                               "support": sha(SUPPORT)}}
    with (HERE / "pair_roots.json").open("x") as out:
        json.dump(root_receipt, out, separators=(",", ":"), sort_keys=True)
        out.write("\n")
    table_receipt = {"status": "PASS_COMPLETE_W15_PAIR_OUTPUT_PREFIX_TABLE",
                     "curve_id": protocol["curve_id"], "target_count": 0,
                     "prefix_bits": protocol["prefix_bits"],
                     "tables": tables,
                     "elapsed_seconds": time.monotonic()-started,
                     "sampled_peak_process_rss_bytes": peak_rss,
                     "sha256": {"producer": sha(Path(__file__)),
                                "protocol": sha(HERE / "projection_protocol.json"),
                                "roots": sha(HERE / "pair_roots.json")}}
    with (HERE / "prefix_table.json").open("x") as out:
        json.dump(table_receipt, out, separators=(",", ":"), sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": table_receipt["status"],
                      "prefixes": [len(t["allowed_prefixes"]) for t in tables],
                      "clauses": [len(t["forbidden_prefixes"]) for t in tables],
                      "elapsed_seconds": table_receipt["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
