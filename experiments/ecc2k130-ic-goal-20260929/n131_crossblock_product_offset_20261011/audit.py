"""Direct source-pair and field-product replay independent of the Walsh producer."""

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SAMPLES = [1, 7, 31, 13686, 87708, 123000, 183094, 262143]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def support(path):
    result = {}
    for text in path.read_text().splitlines():
        mask, column = map(int, text.split())
        assert mask not in result
        result[mask] = column
    return result


def product(a, b, degree, modulus):
    value = 0
    while b:
        if b & 1:
            value ^= a
        a <<= 1
        b >>= 1
    while value.bit_length() > degree:
        value ^= modulus << (value.bit_length() - degree - 1)
    return value


def direct_links(columns, seeds, degree):
    totals = {seed: [0, 0, 0] for seed in seeds}
    for u in range(1, 32):
        translated = {w for w, column in columns.items()
                      if (w ^ u) in columns and column != columns[w ^ u]}
        for seed in seeds:
            if seed == u:
                continue
            c = sum((w ^ seed) in translated for w in translated)
            assert c % 2 == 0
            for index, cap in enumerate((7, 15, 31)):
                if u <= cap:
                    totals[seed][index] += 8 * c
    return totals


def replay(name, degree, samples, expected_support):
    source = HERE / "support_n41.tsv" if name == "n41" else \
        BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
    columns = support(source)
    assert len(columns) == expected_support
    with (HERE / f"per_seed_{name}.tsv").open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert len(rows) == (1 << degree) - 1
    assert [int(row["seed"]) for row in rows] == list(range(1, 1 << degree))
    direct = direct_links(columns, samples, degree)
    for seed, values in direct.items():
        row = rows[seed - 1]
        assert values == [int(row[f"linked_u{k}"]) for k in (7, 15, 31)]
    field_degree = 41 if name == "n41" else 131
    modulus = (1 << field_degree) | ((1 << 3) | 1 if name == "n41" else
                                      (1 << 13) | (1 << 2) | (1 << 1) | 1)
    # Source masks represent coefficients t^1,...,t^d; test the product-offset identity.
    seed = 7 if name == "n41" else 13686
    witness = None
    for u in range(1, 32):
        if u == seed:
            continue
        for w in columns:
            masks = (w, w ^ seed, w ^ u, w ^ seed ^ u)
            if len(set(masks)) != 4 or any(mask not in columns for mask in masks):
                continue
            if len({columns[mask] for mask in masks}) != 4:
                continue
            a, b, c, d = (mask << 1 for mask in masks)
            lhs = product(a, b, field_degree, modulus) ^ \
                  product(c, d, field_degree, modulus)
            us = u << 1
            ss = seed << 1
            rhs = product(us, us, field_degree, modulus) ^ \
                  product(ss, us, field_degree, modulus)
            assert lhs == rhs
            witness = {"seed": seed, "translation": u, "masks": list(masks),
                       "product_offset": str(lhs)}
            break
        if witness:
            break
    assert witness
    return {"direct_seeds_checked": len(samples),
            "direct_seed_values": {str(seed): values for seed, values in direct.items()},
            "product_identity_witness": witness}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    receipt = json.loads((HERE / "receipt.json").read_text())
    summary = json.loads((HERE / "summary.json").read_text())
    assert receipt["status"] == "COMPLETE"
    assert receipt["protocol_sha256"] == digest(HERE / "protocol.json")
    assert summary["summary_protocol_sha256"] == digest(HERE / "summary_protocol.json")
    for row in receipt["cases"]:
        assert row["output_sha256"] == digest(HERE / f"per_seed_{row['name']}.tsv")
        assert row["status"] == "COMPLETE" and row["returncode"] == 0
        assert row["peak_child_rss_bytes"] < protocol["rss_cap_bytes"]
    n41 = replay("n41", 6, list(range(1, 64)), 32)
    n131 = replay("n131", 18, SAMPLES, 131307)
    for name in ("n41", "n131"):
        free = summary["fields"][name]["free_signed_pair_states_N"]
        order = int(summary["fields"][name]["subgroup_order"])
        with (HERE / f"per_seed_{name}.tsv").open(newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        for cap in (7, 15, 31):
            e = sum(int(row[f"linked_u{cap}"]) ** 2 for row in rows)
            claim = summary["fields"][name]["translation_caps"][str(cap)]
            assert str(e) == claim["linked_two_slot_tuple_ceiling_E"]
            assert (order + 2 * free * e - 1) // (2 * free * e) == \
                claim["minimum_target_independent_first_pair_prefixes_q50"]
    result = {"status": "PASS_CROSSBLOCK_TRANSLATION_SUPPORT_AUDIT",
              "protocol_sha256": digest(HERE / "protocol.json"),
              "summary_sha256": digest(HERE / "summary.json"),
              "n41": n41, "n131": n131}
    path = HERE / "audit.json"
    if path.exists():
        assert json.loads(path.read_text()) == result
    else:
        with path.open("x") as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write("\n")
    print(result["status"])


if __name__ == "__main__":
    main()
