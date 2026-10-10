#!/usr/bin/env python3
"""Frozen positive/uniform panel for the W14 high-prefix pair inverse."""

import hashlib
import json
from pathlib import Path
import resource
import statistics
import sys
import time

import prefix

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_polynomial_pair_inverse_20261010"
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009"
PANEL = (0, 8, 16, 20, 24, 28, 30, 31, 32, 33, 34, 35, 36, 40, 48)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_HIGH_PREFIX"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    inputs = json.loads((SOURCE / "inputs.json").read_text())
    assert inputs["status"] == "FROZEN_INPUTS"
    assert tuple(protocol["free_low_bit_widths"]) == PANEL
    assert len(inputs["positives"]) == len(inputs["controls"])-2 == 32
    started = time.monotonic_ns()
    candidate = prefix.oracle.PairOracle(
        prefix.oracle.load_support(SUPPORT / "support_w14.tsv"))
    setup_ns = time.monotonic_ns() - started
    masks = {}
    mask_ns = {}
    for b in PANEL:
        t0 = time.monotonic_ns()
        masks[b] = prefix.invariant_mask(candidate.field, b,
                                         candidate.product_basis)
        mask_ns[b] = time.monotonic_ns() - t0
        assert prefix.popcount(masks[b]) >= max(0, 104-2*b)
    rows = []
    query_start = time.monotonic_ns()
    for b in PANEL:
        for index in range(32):
            for kind, item in (("positive", inputs["positives"][index]),
                               ("uniform_field", inputs["controls"][index])):
                t0 = time.monotonic_ns()
                detail = prefix.inspect_prefix(candidate, item["z"], b,
                                               masks[b], max_nullity=8)
                query_ns = time.monotonic_ns() - t0
                expected = (sorted(item["masks"]) if kind == "positive"
                            else None)
                if (kind == "positive" and detail["status"] != "RANK_FALLBACK"
                        and expected not in detail["pairs"]):
                    raise ValueError(f"positive pair lost at b={b}, index={index}")
                rows.append({"kind": kind, "index": index, "z": item["z"],
                             "expected_pair": expected,
                             "query_ns": query_ns, **detail})
                if ((time.monotonic_ns() - started)/1e9 >
                        protocol["wall_cap_seconds"] or
                        peak_rss() >= protocol["rss_cap_bytes"]):
                    raise RuntimeError(f"panel resource cap at b={b}, index={index}")
    query_ns = time.monotonic_ns() - query_start
    comparisons = []
    for index in range(32):
        for kind, item in (("positive", inputs["positives"][index]),
                           ("uniform_field", inputs["controls"][index])):
            t0 = time.monotonic_ns()
            exact, detail = candidate.joint(item["z"])
            elapsed = time.monotonic_ns() - t0
            row = next(row for row in rows if row["kind"] == kind and
                       row["index"] == index and row["free_low_bits"] == 0)
            if [list(pair) for pair in exact] != row["pairs"]:
                raise ValueError(f"full-output oracle disagreement: {kind} {index}")
            comparisons.append({"kind": kind, "index": index,
                                "source_joint_status": detail["status"],
                                "source_joint_ns": elapsed})
    summaries = []
    for b in PANEL:
        for kind in ("positive", "uniform_field"):
            subset = [row for row in rows if row["free_low_bits"] == b and
                      row["kind"] == kind]
            hist = {}
            for row in subset:
                hist[row["status"]] = hist.get(row["status"], 0) + 1
            summaries.append({"free_low_bits": b, "kind": kind,
                              "invariant_rows": prefix.popcount(masks[b]),
                              "status_histogram": hist,
                              "minimum_rank": min(row["projected_rank"] for row in subset),
                              "maximum_nullity": max(row["nullity"] for row in subset),
                              "recovered_positive_pairs": sum(
                                  kind == "positive" and
                                  row["expected_pair"] in row["pairs"]
                                  for row in subset),
                              "uniform_prefix_hits": sum(bool(row["pairs"])
                                                         for row in subset),
                              "median_query_ns": statistics.median(
                                  row["query_ns"] for row in subset)})
    result = {"status": "COMPLETE_HIGH_PREFIX_PANEL",
              "proposal_id": protocol["proposal_id"], "candidate_id": None,
              "curve_id": protocol["curve_id"], "target_count": 0,
              "panel": list(PANEL), "mask_build_ns": mask_ns,
              "invariant_masks": {str(b): masks[b] for b in PANEL},
              "setup_ns": setup_ns, "query_panel_ns": query_ns,
              "total_wall_ns": time.monotonic_ns() - started,
              "peak_rss_bytes": peak_rss(),
              "rows": rows, "summaries": summaries,
              "full_output_comparisons": comparisons,
              "sha256": {"source": sha(Path(__file__)),
                         "protocol": sha(HERE / "protocol.json"),
                         "prefix": sha(HERE / "prefix.py"),
                         "inputs": sha(SOURCE / "inputs.json")}}
    with output.open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"status": result["status"],
                      "total_wall_seconds": result["total_wall_ns"]/1e9,
                      "peak_rss_bytes": result["peak_rss_bytes"],
                      "summaries": summaries}, sort_keys=True))


if __name__ == "__main__":
    main()
