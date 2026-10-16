#!/usr/bin/env python3
"""Build analysis/profile_local.json, the probe-path profile (diagnostic only).

Inputs, all from the cloud-agent VM (shared 4 vCPU guest; its clocks are not
evidence, and nothing here is a speedup claim):

* `smoke/profile/timing_k600_thp_w11.json`: the profiler
  (`make_profile_source.py`, `KIC_PROBE_PROFILE=400:7`) on the frozen K600
  base, target w11 (B's fresh point 11), with glibc's
  `glibc.malloc.hugetlb=1` so the 4 GiB root table is THP-backed as on the
  runner (whose THP mode is `always`). Cumulative variants; the minimum over
  7 rounds per variant; differences are marginal ns/probe.
* `smoke/profile/callgrind_summaries.txt`: callgrind total instructions for
  each variant with 1 and 2 passes on a small constructed base
  (`construct:83:1:40`, 200 states of w11's Feistel order, 66,400 probes);
  the difference of the two totals is one pass, so setup cancels.
  Instruction counts per probe do not depend on the table size.
* `smoke/profile/producer_k600_thp_off.json`: the real producer
  (`KIC_PROBE_PIPELINE=off`, the combined probe loop) on w11, w08, w14 with
  the same THP setting; its online ns/probe minus the `inline_lookup`
  variant is "the rest" (hits, lift, relation check, clock laps, state
  order).
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PROFILE = HERE / "smoke" / "profile"
PROBES_CG = 66400


def main():
    timing = json.loads((PROFILE / "timing_k600_thp_w11.json").read_text().strip().splitlines()[-1])
    v = {k: x["ns_per_probe_min"] for k, x in timing["variants"].items()}
    cg = {}
    for line in (PROFILE / "callgrind_summaries.txt").read_text().splitlines():
        variant, passes, _, total = line.split()
        cg.setdefault(int(variant), {})[int(passes)] = int(total)
    ir = {k: (p[2] - p[1]) / PROBES_CG for k, p in cg.items()}
    producer = json.loads((PROFILE / "producer_k600_thp_off.json").read_text())
    real = sum(r["online_ms"] for r in producer) * 1e6 / sum(r["probes"] for r in producer)
    rows = [
        ("root_solve", "2n candidate inputs (to_poly of rotated stored roots) and the batched S3 root solve "
                       "(Montgomery batch inversion)", v["roots"], ir[0]),
        ("conversion", "to_normal byte-table conversion of each partner root", v["roots_conv"] - v["roots"],
         ir[1] - ir[0]),
        ("canonicalization", "lift_scan canonical rotation", v["roots_conv_canon"] - v["roots_conv"], ir[2] - ir[1]),
        ("lookup", "root-table probe into the 4 GiB table, in the combined loop's interleaved order",
         v["inline_lookup"] - v["roots_conv_canon"], ir[3] - ir[2]),
        ("rest", "everything else in the real producer's online interval (hits, lift, relation check, laps, "
                 "Feistel order)", real - v["inline_lookup"], None),
    ]
    total = real
    table = [{"component": c, "what": w, "ns_per_probe": ns, "share_of_real": ns / total,
              "instructions_per_probe": i} for c, w, ns, i in rows]
    out = {
        "status": "diagnostic (cloud-agent VM, shared 4 vCPU guest); chose the fix; not a speedup claim",
        "target": "w11", "states": timing["states"], "probes": timing["probes"], "rounds": timing["rounds"],
        "table_policy": "THP via GLIBC_TUNABLES=glibc.malloc.hugetlb=1 (runner: THP always)",
        "real_producer_ns_per_probe": real,
        "real_producer_points": ["w11", "w08", "w14"],
        "components": table,
        "pipelined_lookup_ns_per_probe": v["pipelined_lookup"] - v["roots_conv_canon"],
        "pipelined_lookup_instructions_per_probe": ir[4] - ir[2],
        "cross_state_pipelined_lookup_ns_per_probe": v["cross_state_pipelined"] - v["roots_conv_canon"],
        "lookup_only_dependent_ns": v["lookup_dependent"],
        "lookup_only_independent_ns": v["lookup_independent"],
        "variant_ns_per_probe_min": v,
        "callgrind_instructions_per_probe_cumulative": {timing_name: ir[k] for k, timing_name in
                                                        enumerate(["roots", "roots_conv", "roots_conv_canon",
                                                                   "inline_lookup", "pipelined_lookup"])},
        "dominant": "lookup",
        "summary": ("diagnostic, VM: lookup %.0f ns/probe (%.0f%% of %.0f) but %.0f instructions; root solve %.0f ns "
                    "(%.0f%%); canonicalization %.0f ns (%.0f%%); conversion %.0f ns (%.0f%%); rest %.0f ns. The "
                    "lookup is latency-bound: few instructions, most of the time. Prefetch-pipelining the state's "
                    "probes cut the in-situ lookup to %.0f ns/probe in the profiler." %
                    (table[3]["ns_per_probe"], 100 * table[3]["share_of_real"], real, table[3]["instructions_per_probe"],
                     table[0]["ns_per_probe"], 100 * table[0]["share_of_real"], table[2]["ns_per_probe"],
                     100 * table[2]["share_of_real"], table[1]["ns_per_probe"], 100 * table[1]["share_of_real"],
                     table[4]["ns_per_probe"], v["pipelined_lookup"] - v["roots_conv_canon"])),
    }
    (HERE / "analysis" / "profile_local.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(out["summary"])
    for row in table:
        print(row["component"], round(row["ns_per_probe"], 1), round(100 * row["share_of_real"], 1),
              None if row["instructions_per_probe"] is None else round(row["instructions_per_probe"], 1))


if __name__ == "__main__":
    main()
