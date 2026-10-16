#!/usr/bin/env python3
"""Build analysis/profile_local.json, the root-table lookup diagnosis (diagnostic only).

Inputs, all from the cloud-agent VM (shared 4 vCPU Intel Xeon guest; its
clocks are not evidence, and nothing here is a speedup claim):

* `smoke/profile/profile_k600_thp_w11.json`: the profiler
  (`make_profile_source.py`, `KIC_PROBE_PROFILE=400:7`) on the frozen K600
  base, target w11, with `GLIBC_TUNABLES=glibc.malloc.hugetlb=1` so every
  table is THP-backed as on the runner (THP `always` there). 400 states of
  w11's Feistel order, 132,800 probes, 7 rounds in rotated order; the
  median over rounds per variant. Cumulative in-situ variants: differences
  are marginal ns/probe.
* `smoke/profile/profile_k600_4k_w11.json`: the same with
  `glibc.malloc.hugetlb=0` (4 KiB pages; THP is `madvise` on this VM), the
  page-size manipulation.

The 4 GiB base table's slot is 32 bytes (`(u128, u64)` padded to 16-byte
alignment), 2^27 slots at load 0.22 (29,878,182 keys).
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PROFILE = HERE / "smoke" / "profile"


def variants(name):
    record = json.loads((PROFILE / name).read_text().strip().splitlines()[-1])
    return record, {k: x["ns_per_probe_median"] for k, x in record["variants"].items()}


def main():
    thp_record, thp = variants("profile_k600_thp_w11.json")
    _, small = variants("profile_k600_4k_w11.json")
    compute = thp["roots_conv_canon"]

    def marginal(v, key):
        return v[key] - v["roots_conv_canon"]

    rows = []
    for key, what in (("inline_lookup", "base 4 GiB table, the combined loop (key, lookup, next key)"),
                      ("pipelined_lookup", "base 4 GiB table, the probe pipeline (all keys + prefetch, then lookups)"),
                      ("compact_pipelined", "16-byte compact 2 GiB table, the same pipeline"),
                      ("filter_pipelined", "32 MiB blocked filter in front of the compact table "
                                           "(filter prefetch, filter test, survivors' slot prefetch, survivors' lookups)")):
        rows.append({"variant": key, "what": what, "lookup_ns_per_probe_thp": marginal(thp, key),
                     "lookup_ns_per_probe_4k": marginal(small, key)})
    lookup_only = {key: {"thp": thp[key], "4k": small[key]} for key in (
        "lookup_dependent", "lookup_independent", "lookup_prefetched_base",
        "lookup_independent_compact", "lookup_prefetched_compact",
        "lookup_independent_filter", "lookup_prefetched_filter")}
    tables = thp_record["root_tables"]
    out = {
        "status": "diagnostic, cloud-agent VM (Intel Xeon guest); chose the design, is not evidence of a speedup",
        "probes": thp_record["probes"], "states": thp_record["states"], "rounds": thp_record["rounds"],
        "compute_ns_per_probe_roots_conv_canon": compute,
        "in_situ_lookup": rows,
        "lookup_only_ns_per_probe": lookup_only,
        "root_tables": tables,
        "filter_false_positive_rate_profiled": tables["filter_survivors_per_round"] / thp_record["probes"],
        "summary": {
            "base_pipelined_lookup_ns": marginal(thp, "pipelined_lookup"),
            "compact_pipelined_lookup_ns": marginal(thp, "compact_pipelined"),
            "filter_pipelined_lookup_ns": marginal(thp, "filter_pipelined"),
            "prefetch_gain_base_lookup_only": thp["lookup_independent"] / thp["lookup_prefetched_base"],
            "prefetch_gain_filter_lookup_only": thp["lookup_independent_filter"] / thp["lookup_prefetched_filter"],
            "4k_over_thp_base_pipelined": marginal(small, "pipelined_lookup") / marginal(thp, "pipelined_lookup"),
            "4k_over_thp_filter_prefetched": small["lookup_prefetched_filter"] / thp["lookup_prefetched_filter"],
            "reading": "Prefetch does not overlap lookups into the 2-4 GiB tables (lookup-only: prefetched about "
                       "as slow as unprefetched; in situ ~140 ns per probe remain), halving the slot to 16 bytes "
                       "changes almost nothing, and 4 KiB pages make the big tables much slower while the 32 MiB "
                       "filter is unchanged and its prefetches do overlap. The limit is address translation "
                       "for a working set far beyond TLB reach (page walks whose own entries miss the caches, "
                       "few walks in flight), not bytes per slot; a small filter whose translations stay "
                       "resident removes it for the ~97.6% of probes it rejects.",
        },
    }
    (HERE / "analysis" / "profile_local.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["summary"], indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
