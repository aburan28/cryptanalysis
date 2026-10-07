#!/usr/bin/env python3
"""Independent Sage group replay of the coset-aware scalar selector."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from coset_selector import FIXTURES
from mixed_atlas_screen import make_options
from mixed_radix_scalar import source_cost
from screen_coset_representatives import candidates
from screen_radix_policy import recode
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F


def check_fixture(path, tables, options, panel):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    curve = EllipticCurve(GF(P), [0, 7])
    beta = curve.base_field()(int(fixture["beta_hex"], 16))
    assert beta**3 == 1 and beta != 1
    cache = {}
    digest = hashlib.sha256()
    choices = {"selective": 0, "zero_tau_rank0": 0,
               "zero_tau_rank1": 0, "zero_tau_rank2": 0}
    nonzero = 0
    assert len(fixture["cases"]) == len(panel["rows"])
    for case, row in zip(fixture["cases"], panel["rows"]):
        assert case["index"] == row["index"]
        key = (case["base_x_hex"], case["base_y_hex"])
        if key not in cache:
            base = curve(int(key[0], 16), int(key[1], 16))
            tau_base = base - curve(beta * base[0], base[1])
            cache[key] = base, tau_base, {}
        base, tau_base, digit_points = cache[key]
        short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        representatives = candidates(int(case["scalar_hex"], 16))[:3]
        assert representatives[0][2:4] == short
        if row["selected_kind"] == "selective":
            choice = "selective"
            old_digits, old_score = selective_recode(short, tables, options)
            assert old_score["total_M_plus_S"] == row["selected_M_plus_S"]
            stream = [("tau", (digit[0], digit[1]) if digit else None,
                       digit[2] if digit else None) for digit in old_digits]
        else:
            rank = row["selected_norm_rank"]
            assert rank in (0, 1, 2) and row["selected_path_index"] == rank + 1
            choice = f"zero_tau_rank{rank}"
            a, b = representatives[rank][2:4]
            assert (a, b) == (int(row["paths"][rank + 1]["a_hex"], 16),
                              int(row["paths"][rank + 1]["b_hex"], 16))
            stream, status = recode((a, b), tables[0], "skip_zero_tau")
            assert status == "verified" and stream is not None
            assert source_cost(stream)["total_M_plus_S"] == row["selected_M_plus_S"]
        choices[choice] += 1
        accumulator = curve(0)
        for radix, digit, _ in reversed(stream):
            if radix == "two":
                accumulator += accumulator
            elif accumulator != curve(0):
                accumulator -= curve(beta * accumulator[0], accumulator[1])
            if digit is None:
                continue
            if digit not in digit_points:
                digit_points[digit] = digit[0] * base + digit[1] * tau_base
            accumulator += digit_points[digit]
            nonzero += 1
        expected = (curve(0) if case.get("expected_identity", False) else
                    curve(int(case["expected_x_hex"], 16), int(case["expected_y_hex"], 16)))
        assert accumulator == expected, f"scalar mismatch {path.name}:{case['index']}"
        digest.update(key[0].encode())
        digest.update(case["scalar_hex"].encode())
        digest.update(b"identity" if accumulator == curve(0) else
                      f"{int(accumulator[0]):064x}{int(accumulator[1]):064x}".encode())
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(fixture["cases"]),
            "base_points": len(cache),
            "choices": choices,
            "nonzero_digit_additions": nonzero,
            "output_digest_sha256": digest.hexdigest(),
            "verified": True}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    scores = json.loads((HERE / "coset-result.json").read_bytes())
    panels = [check_fixture(path, tables, options, panel)
              for path, panel in zip(FIXTURES, scores["panels"])]
    assert [panel["cases"] for panel in panels] == [64, 256]
    result = {"schema": 1, "curve": "secp256k1", "verified": True,
              "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "recoder_sha256": hashlib.sha256((HERE / "coset_selector.py").read_bytes()).hexdigest(),
              "runtime_info_sha256": hashlib.sha256((HERE / "coset-runtime-info.json").read_bytes()).hexdigest(),
              "cpu_speedup_claim": None}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
