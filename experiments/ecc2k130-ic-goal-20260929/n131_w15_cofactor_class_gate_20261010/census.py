#!/usr/bin/env sage -python
"""Census the exact 4E-class bit on the full W15 coordinate subspace."""

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import psutil
from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
WIDTH = 15


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def halftrace(value):
    total = value.parent().zero()
    term = value
    for _ in range(66):
        total += term
        term = term**4
    assert total**2 + total == value
    return total


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_COFACTOR_CLASS_CENSUS"
    assert protocol["sha256"]["census"] == sha(Path(__file__))
    assert protocol["sha256"]["support"] == sha(SUPPORT)
    assert protocol["sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    assert not (HERE / "class_bits.bin").exists()
    assert not (HERE / "census.json").exists()
    started = time.monotonic()
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    basis_w = [field.gen()**i for i in range(1, WIDTH+1)]
    basis_v = [halftrace(w**2) for w in basis_w]
    bits = bytearray(1 << WIDTH)
    for mask in range(1, 1 << WIDTH):
        w = sum((basis_w[i] for i in range(WIDTH) if mask >> i & 1),
                field.zero())
        v = sum((basis_v[i] for i in range(WIDTH) if mask >> i & 1),
                field.zero())
        bits[mask] = int((v/w).trace())
        if mask % 4096 == 0:
            peak_rss = max(peak_rss, process.memory_info().rss)
            elapsed = time.monotonic()-started
            print(json.dumps({"masks_done": mask,
                              "elapsed_seconds": elapsed,
                              "sampled_peak_rss_bytes": peak_rss}), flush=True)
            if elapsed >= protocol["wall_cap_seconds"] or peak_rss >= protocol["rss_cap_bytes"]:
                failure = {"status": "CENSORED_RESOURCE_GATE", "masks_done": mask,
                           "elapsed_seconds": elapsed,
                           "sampled_peak_rss_bytes": peak_rss,
                           "protocol_sha256": sha(HERE / "protocol.json")}
                with (HERE / "census_failure.json").open("x") as out:
                    json.dump(failure, out, indent=2, sort_keys=True)
                    out.write("\n")
                raise SystemExit(2)
    columns = defaultdict(list)
    for line in SUPPORT.read_text().splitlines():
        mask, column = map(int, line.split())
        columns[column].append(mask)
    assert len(columns) == 16381
    support_masks = [mask for masks in columns.values() for mask in masks]
    assert len(support_masks) == 16441
    support_classes = Counter(bits[mask] for mask in support_masks)
    assert set(support_classes) == {0, 1}
    mixed_columns = [col for col, masks in columns.items()
                     if len({bits[mask] for mask in masks}) != 1]
    pair_class0 = (support_classes[0]*(support_classes[0]-1)//2
                   +support_classes[1]*(support_classes[1]-1)//2
                   -sum(sum((count*(count-1)//2)
                            for count in Counter(bits[mask] for mask in masks).values())
                        for masks in columns.values()))
    pair_class1 = support_classes[0]*support_classes[1]
    # If a folded column mixed classes, subtract its cross-class pairs.
    for col in mixed_columns:
        masks = columns[col]
        zeros = sum(bits[mask] == 0 for mask in masks)
        ones = len(masks)-zeros
        pair_class1 -= zeros*ones
    assert 4*(pair_class0+pair_class1) == 540579832
    anf = bytearray(bits)
    for bit in range(WIDTH):
        step = 1 << bit
        for mask in range(1 << WIDTH):
            if mask & step:
                anf[mask] ^= anf[mask ^ step]
    degrees = Counter(mask.bit_count() for mask, value in enumerate(anf) if value)
    degree = max(degrees)
    (HERE / "class_bits.bin").write_bytes(bits)
    result = {
        "status": "PASS_EXACT_W15_COFACTOR_CLASS_CENSUS",
        "curve_id": protocol["curve_id"],
        "mask_width": WIDTH,
        "class_definition": "0 iff a source point lies in 4E, computed as Tr(H(w^2)/w)",
        "full_subspace_masks_including_zero": len(bits),
        "rational_support_masks": len(support_masks),
        "support_class_counts": {str(k): v for k, v in sorted(support_classes.items())},
        "mixed_folded_columns": mixed_columns,
        "signed_unordered_pair_states_by_output_class": {
            "0": 4*pair_class0, "1": 4*pair_class1},
        "anf_degree": degree,
        "anf_monomials_by_degree": {str(k): v for k, v in sorted(degrees.items())},
        "anf_monomials_total": sum(degrees.values()),
        "elapsed_seconds": time.monotonic()-started,
        "sampled_peak_rss_bytes": max(peak_rss, process.memory_info().rss),
        "sha256": {"protocol": sha(HERE / "protocol.json"),
                   "source": sha(Path(__file__)),
                   "class_bits": sha(HERE / "class_bits.bin"),
                   "support": sha(SUPPORT)}}
    with (HERE / "census.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "support_classes": result["support_class_counts"],
                      "anf_degree": degree,
                      "anf_monomials_total": result["anf_monomials_total"],
                      "elapsed_seconds": result["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
