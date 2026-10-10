#!/usr/bin/env python3
"""Frozen nested W15..W18 support and same-seed six-pair capacity count."""
import collections
import hashlib
import json
import resource
import subprocess
import sys
import time
from decimal import Decimal, getcontext
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ORDER = 680564733841876926932320129493409985129
getcontext().prec = 50


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fwht(values):
    step = 1
    while step < len(values):
        view = values.reshape(-1, 2*step)
        left = view[:, :step].copy()
        right = view[:, step:].copy()
        view[:, :step] = left + right
        view[:, step:] = left - right
        step *= 2
    return values


def count_width(degree, support, source_receipt):
    started = time.monotonic_ns()
    rows = [tuple(map(int, line.split())) for line in support.read_text().splitlines()]
    expected = source_receipt["widths"][degree-15]
    assert expected["degree"] == degree
    assert len(rows) == expected["rational_masks"]
    indicator = np.zeros(1 << degree, dtype=np.int64)
    by_column = collections.defaultdict(list)
    for mask, column in rows:
        assert 0 < mask < len(indicator) and indicator[mask] == 0
        indicator[mask] = 1
        by_column[column].append(mask)
    assert len(by_column) == expected["folded_columns_K"]
    spectrum = fwht(indicator)
    correlation = fwht(spectrum * spectrum)
    assert np.all(correlation % len(correlation) == 0)
    correlation //= len(correlation)
    signed = 2*correlation
    signed[0] = 0
    same_column_pairs = 0
    for masks in by_column.values():
        for index, first in enumerate(masks):
            for second in masks[index+1:]:
                signed[first ^ second] -= 4
                same_column_pairs += 1
    assert int(signed.min()) >= 0 and np.all(signed % 4 == 0)
    total = int(signed.sum())
    unordered = total // 4
    assert unordered == len(rows)*(len(rows)-1)//2 - same_column_pairs
    same_seed = int(np.dot(signed, signed))
    tuples = total*total*same_seed*same_seed
    suffix = total*same_seed*same_seed
    prefixes = (ORDER + 2*suffix - 1)//(2*suffix)
    return {"degree": degree, "rational_masks": len(rows),
            "folded_columns_K": len(by_column),
            "actual_factor_base_B": expected["actual_projected_factor_base_B"],
            "accepted_unordered_mask_pairs": unordered,
            "excluded_same_column_unordered_pairs": same_column_pairs,
            "signed_pair_states_N": total,
            "same_seed_two_pair_states_M": same_seed,
            "minimum_nonzero_seed_states": int(signed[1:].min()),
            "maximum_nonzero_seed_states": int(signed[1:].max()),
            "seed_count_sha256_i64le": hashlib.sha256(
                signed.astype("<i8").tobytes()).hexdigest(),
            "six_pair_tuple_ceiling": str(tuples),
            "mean_tuples_per_uniform_subgroup_target": str(Decimal(tuples)/Decimal(ORDER)),
            "minimum_one_free_pair_prefixes_for_half_union_ceiling": prefixes,
            "necessary_average_microseconds_per_prefix_in_600s": str(
                Decimal(600_000_000)/Decimal(prefixes)),
            "support_sha256": sha(support),
            "count_wall_ns": time.monotonic_ns()-started}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SOURCE_AND_COUNT"
    paths = {"count": HERE / "count.py", "export_source": HERE / "export_support.cpp",
             "export_binary": HERE / "export_support",
             "compiler_version": HERE / "compiler_version.txt",
             "field_library": ROOT.parent / "koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp",
             "archived_w15_support": ROOT / "n131_w15_coupled_sixpair_20261010/support_w15.tsv",
             "archived_w15_count": ROOT / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json"}
    assert protocol["source_sha256"] == {name: sha(path) for name, path in paths.items()}
    assert not (HERE / "result.json").exists()
    assert not (HERE / "support_receipt.json").exists()
    started = time.monotonic_ns()
    command = [str(paths["export_binary"].resolve()), str(HERE.resolve())]
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=protocol["wall_cap_seconds"], check=False)
    (HERE / "export.stdout.txt").write_text(result.stdout)
    (HERE / "export.stderr.txt").write_text(result.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"source exporter failed: {result.returncode}")
    source_receipt = json.loads((HERE / "support_receipt.json").read_text())
    assert source_receipt["status"] == "COMPLETE_NESTED_W15_W18_SUPPORT"
    assert sha(HERE / "support_w15.tsv") == sha(paths["archived_w15_support"])
    widths = [count_width(degree, HERE / f"support_w{degree}.tsv", source_receipt)
              for degree in range(15, 19)]
    archived = json.loads(paths["archived_w15_count"].read_text())
    assert widths[0]["signed_pair_states_N"] == archived[
        "accepted_signed_pair_states_per_rotation"]
    assert widths[0]["same_seed_two_pair_states_M"] == archived[
        "same_seed_two_pair_states"]
    assert widths[0]["six_pair_tuple_ceiling"] == archived["six_pair_tuple_count"]
    assert widths[0]["actual_factor_base_B"] == archived["factor_base_B"]
    assert widths[-1]["rational_masks"] == protocol["expected_w18_rational_masks"]
    elapsed = time.monotonic_ns()-started
    peak_self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform != "darwin":
        peak_self *= 1024
        peak_child *= 1024
    peak = max(peak_self, peak_child)
    status = "PASS_N131_W15_W18_WIDTH_GATE"
    if elapsed > protocol["wall_cap_seconds"]*10**9:
        status = "CENSORED_TIME"
    if peak > protocol["rss_cap_bytes"]:
        status = "CENSORED_MEMORY"
    record = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "target_count": 0,
              "policy": protocol["policy"], "widths": widths,
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": sha(HERE / "protocol.json"),
              "support_receipt_sha256": sha(HERE / "support_receipt.json"),
              "export_stdout_sha256": sha(HERE / "export.stdout.txt"),
              "export_stderr_sha256": sha(HERE / "export.stderr.txt"),
              "wall_ns": elapsed, "peak_rss_bytes": peak}
    (HERE / "result.json").write_text(json.dumps(record, sort_keys=True,
                                                 indent=2) + "\n")
    print(json.dumps({"status": status, "widths": [
        {"d": row["degree"], "B": row["actual_factor_base_B"],
         "mean": row["mean_tuples_per_uniform_subgroup_target"],
         "prefixes": row["minimum_one_free_pair_prefixes_for_half_union_ceiling"]}
        for row in widths], "wall_ns": elapsed, "peak_rss_bytes": peak}))


if __name__ == "__main__":
    main()
