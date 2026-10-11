"""Exact large-integer source ceilings for the translated cross-block policy."""

import csv
import hashlib
import json
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "summary_protocol.json").read_text())
    files = {"summarizer": HERE / "summarize.py",
             "census_protocol": HERE / "protocol.json", "census_receipt": HERE / "receipt.json",
             "n41_counts": HERE / "per_seed_n41.tsv", "n131_counts": HERE / "per_seed_n131.tsv",
             "n41_generator": BASE / "n41_w6_public_seed_predictor_20261011/generator_receipt.json",
             "n131_width_gate": BASE / "n131_w16_w18_sixpair_width_gate_20261010/result.json"}
    assert protocol["source_sha256"] == {key: digest(path) for key, path in files.items()}
    assert json.loads(files["census_receipt"].read_text())["status"] == "COMPLETE"
    width = json.loads(files["n131_width_gate"].read_text())["widths"][3]
    assert width["degree"] == 18
    free_counts = {
        "n41": json.loads(files["n41_generator"].read_text())["pair_states_per_rotation"],
        "n131": width["signed_pair_states_N"],
    }
    orders = {"n41": 549756390943,
              "n131": 680564733841876926932320129493409985129}
    getcontext().prec = 60
    results = {}
    for name, degree in (("n41", 6), ("n131", 18)):
        with files[f"{name}_counts"].open(newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        assert len(rows) == (1 << degree) - 1
        assert [int(row["seed"]) for row in rows] == list(range(1, 1 << degree))
        kresults = {}
        for k in (7, 15, 31):
            values = [int(row[f"linked_u{k}"]) for row in rows]
            assert all(value >= 0 and value % 16 == 0 for value in values)
            e = sum(value * value for value in values)
            free = free_counts[name]
            order = orders[name]
            prefix_denom = 2 * free * e
            q50 = (order + prefix_denom - 1) // prefix_denom if e else None
            mean = Decimal(free * free * e) / Decimal(order)
            kresults[str(k)] = {
                "nonzero_seeds": sum(value > 0 for value in values),
                "maximum_linked_states_per_seed": max(values),
                "linked_two_slot_tuple_ceiling_E": str(e),
                "six_pair_uniform_target_mean_upper": str(mean),
                "minimum_target_independent_first_pair_prefixes_q50": q50,
                "necessary_average_microseconds_per_prefix_in_600s":
                    str(Decimal(600_000_000) / Decimal(q50)) if q50 else None,
            }
        results[name] = {"degree": degree, "free_signed_pair_states_N": free,
                         "subgroup_order": str(orders[name]), "translation_caps": kresults}
    output = {"status": "EXACT_PRODUCT_TRANSLATION_SUPPORT_CEILINGS",
              "summary_protocol_sha256": digest(HERE / "summary_protocol.json"),
              "source_sha256": protocol["source_sha256"], "fields": results}
    with (HERE / "summary.json").open("x") as stream:
        json.dump(output, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print({name: {k: row["minimum_target_independent_first_pair_prefixes_q50"]
                       for k, row in field["translation_caps"].items()}
           for name, field in results.items()})


if __name__ == "__main__":
    main()
