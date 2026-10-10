#!/usr/bin/env python3
"""Walsh census of pair cofactor class within each W15 XOR seed."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
SIZE = 1 << 15


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walsh(values):
    width = 1
    while width < len(values):
        for start in range(0, len(values), 2*width):
            for i in range(start, start+width):
                a, b = values[i], values[i+width]
                values[i], values[i+width] = a+b, a-b
        width *= 2


def autocorrelation(values):
    transformed = values.copy()
    walsh(transformed)
    squared = [x*x for x in transformed]
    walsh(squared)
    assert all(x % SIZE == 0 for x in squared)
    return [x//SIZE for x in squared]


def main():
    protocol = json.loads((HERE / "seed_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_CLASS_SEED_CENSUS"
    assert protocol["sha256"]["script"] == sha(Path(__file__))
    assert protocol["sha256"]["support"] == sha(SUPPORT)
    assert protocol["sha256"]["class_bits"] == sha(HERE / "class_bits.bin")
    classes = (HERE / "class_bits.bin").read_bytes()
    support = [0]*SIZE
    signed = [0]*SIZE
    columns = defaultdict(list)
    for row in SUPPORT.read_text().splitlines():
        mask, column = map(int, row.split())
        assert not support[mask]
        support[mask] = 1
        signed[mask] = 1 if classes[mask] == 0 else -1
        columns[column].append(mask)
    support_corr = autocorrelation(support)
    signed_corr = autocorrelation(signed)
    alias = Counter(a^b for group in columns.values()
                    for a in group for b in group if a != b)
    class0 = [0]*SIZE
    class1 = [0]*SIZE
    for seed in range(1, SIZE):
        total = support_corr[seed]-alias[seed]
        bias = signed_corr[seed]-alias[seed]
        assert total >= 0 and abs(bias) <= total
        class0[seed] = total+bias
        class1[seed] = total-bias
    census = json.loads((HERE / "census.json").read_text())
    assert sum(class0) == census["signed_unordered_pair_states_by_output_class"]["0"]
    assert sum(class1) == census["signed_unordered_pair_states_by_output_class"]["1"]
    maxima = sorted(range(1, SIZE), key=lambda s: (-class0[s], s))[:10]
    minima = sorted(range(1, SIZE), key=lambda s: (class0[s], s))[:10]
    distribution = {"zero_class0_seeds": sum(x == 0 for x in class0[1:]),
                    "zero_class1_seeds": sum(x == 0 for x in class1[1:]),
                    "min_class0_states": min(class0[1:]),
                    "max_class0_states": max(class0[1:]),
                    "min_class1_states": min(class1[1:]),
                    "max_class1_states": max(class1[1:]),
                    "max_abs_class_bias": max(abs(class0[s]-class1[s])
                                              for s in range(1, SIZE)),
                    "top_class0_seeds": [[s, class0[s], class1[s]] for s in maxima],
                    "bottom_class0_seeds": [[s, class0[s], class1[s]] for s in minima]}
    binary = bytearray()
    for first, second in zip(class0, class1):
        binary.extend(first.to_bytes(4, "little"))
        binary.extend(second.to_bytes(4, "little"))
    (HERE / "seed_class_counts.bin").write_bytes(binary)
    result = {"status": "PASS_EXACT_W15_CLASS_BY_XOR_SEED",
              "seed_count": SIZE-1,
              "counts_record_format": "little-endian uint32 class0,class1 for every seed 0..32767",
              "totals": {"0": sum(class0), "1": sum(class1)},
              "distribution": distribution,
              "sha256": {"protocol": sha(HERE / "seed_protocol.json"),
                         "script": sha(Path(__file__)),
                         "counts": sha(HERE / "seed_class_counts.bin"),
                         "support": sha(SUPPORT),
                         "class_bits": sha(HERE / "class_bits.bin")}}
    with (HERE / "seed_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "distribution": distribution}))


if __name__ == "__main__":
    main()
