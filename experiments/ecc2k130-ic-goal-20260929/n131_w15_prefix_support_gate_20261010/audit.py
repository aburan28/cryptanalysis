#!/usr/bin/env python3
"""Independent integer and rational replay of the prefix-support receipt."""

from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SOURCES = {
    "freeze": HERE / "freeze.py",
    "calculator": HERE / "calculate.py",
    "independent_audit": Path(__file__),
    "w15_exact_count": BASE / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json",
    "w14_exact_count": BASE / "n41_upper_xor_projection_20261010/seed_sum_count.json",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in SOURCES.items()}
    assert result["source_sha256"] == {
        "protocol": sha(HERE / "protocol.json"),
        **{name: sha(path) for name, path in SOURCES.items()},
    }
    assert result["status"] == "PASS_EXACT_W15_PREFIX_SUPPORT_GATES"
    r = int(protocol["subgroup_order"])
    checks = []
    for width in ("w14", "w15"):
        source = json.loads(SOURCES[f"{width}_exact_count"].read_text())
        if width == "w14":
            source = source["n131"]
            n = int(source["signed_pair_states_per_rotation"])
        else:
            n = int(source["accepted_signed_pair_states_per_rotation"])
        m = int(source["same_seed_two_pair_states"])
        total = int(source["six_pair_tuple_count"])
        saved = result["records"][width]
        assert total == int(saved["six_pair_tuple_count"])
        assert total == n * n * m * m
        assert Fraction(total, r) == Fraction(
            int(saved["group_wide_tuple_mean"]["numerator"]),
            int(saved["group_wide_tuple_mean"]["denominator"]))
        # Derive each suffix by dividing the complete tuple census by the
        # corresponding prefix multiplicity, separately from the producer.
        for label, prefix in (("one_free_pair_fixed", n),
                              ("one_constrained_four_atom_block_fixed", m),
                              ("both_free_pairs_fixed", n * n)):
            cell = saved["partitions"][label]
            assert int(cell["prefix_state_count"]) == prefix
            assert total % prefix == 0
            suffix = total // prefix
            assert int(cell["suffix_tuple_count_upper"]) == suffix
            expected = min(Fraction(suffix, r), Fraction(1))
            observed = Fraction(
                int(cell["uniform_target_occupancy_upper"]["numerator"]),
                int(cell["uniform_target_occupancy_upper"]["denominator"]))
            assert observed == expected
            q = int(cell["distinct_prefixes_needed_before_union_upper_reaches_half"])
            assert Fraction(q * suffix, r) >= Fraction(1, 2)
            assert q == 1 or Fraction((q - 1) * suffix, r) < Fraction(1, 2)
            assert Fraction(
                int(cell["necessary_probe_rate_per_second"]["numerator"]),
                int(cell["necessary_probe_rate_per_second"]["denominator"])) == \
                Fraction(q, protocol["wall_budget_seconds"])
            assert Fraction(
                int(cell["necessary_budget_per_probe_ms"]["numerator"]),
                int(cell["necessary_budget_per_probe_ms"]["denominator"])) == \
                Fraction(1000 * protocol["wall_budget_seconds"], q)
            checks.append(f"{width}:{label}")
    record = {
        "status": "PASS_INDEPENDENT_PREFIX_SUPPORT_ARITHMETIC",
        "checked_partitions": checks,
        "result_sha256": sha(HERE / "result.json"),
        "audit_source_sha256": sha(__file__),
    }
    with (HERE / "audit.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(record["status"])


if __name__ == "__main__":
    main()
