#!/usr/bin/env python3
"""Generate a frozen one-target IC-versus-rho panel for scripts/isolated_bench.py.

Each case is one public target from the frozen scalar law in one_target.py; the reference solves it
with one-target Pollard rho and the candidate with the PDP2ht IC pipeline (walk rerandomization),
on the bases the online-ht suite measured as best (fb-search/online-ht-selected.json):

    n = 19: IC1N19Ckb1fb78PDP2htRCsampleLAgaussTDpdpISO0h286621b6083e   (geomtraceu, l = 6, seed 4)
    n = 23: IC1N23Ckb1fb266PDP2htRCsampleLAgaussTDpdpISO0h33de8ed9a126  (geomtraceu, l = 8, seed 2)

All paths must be absolute on the benchmark host.  Example (topology is the host's):

    python3 experiments/fb-search/isolated/make_ic_isolated_manifest.py \\
      --python /usr/bin/python3 --workdir /workspace/cryptanalysis \\
      --cgroup /sys/fs/cgroup/benchmark-isolated --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \\
      --output /workspace/isolated-bench/ic-rho-panel.json
    python3 scripts/isolated_bench.py probe /workspace/isolated-bench/ic-rho-panel.json
    python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit /workspace/isolated-bench/ic-rho-panel.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PANEL_KEY = "fb06-ic-rho-v1"
BASES = {
    19: {"family": "geomtraceu", "l": 6, "seed": 4,
         "candidate_id": "IC1N19Ckb1fb78PDP2htRCsampleLAgaussTDpdpISO0h286621b6083e"},
    23: {"family": "geomtraceu", "l": 8, "seed": 2,
         "candidate_id": "IC1N23Ckb1fb266PDP2htRCsampleLAgaussTDpdpISO0h33de8ed9a126"},
}
ARTIFACTS = [
    "experiments/fb-search/isolated/one_target.py",
    "experiments/ic-bench/bench.py",
    "experiments/pdp-degree-heuristics/monitor.py",
    "experiments/pdp-degree-heuristics/htsolver.py",
    "experiments/pdp-degree-heuristics/kernel.py",
    "experiments/pdp-degree-heuristics/pdpkernel.c",
    "experiments/pdp-degree-heuristics/toycurve.py",
    "experiments/pdp-degree-heuristics/factor_base.py",
    "experiments/pdp-degree-heuristics/relations.py",
    "experiments/pdp-degree-heuristics/descent.py",
    "experiments/pdp-degree-heuristics/macaulay.py",
    "experiments/pdp-degree-heuristics/opcount.py",
]


def build(python: Path, workdir: Path, cgroup: Path, cpus: str, execution_cpu: int, mem_nodes: str,
          targets: dict[int, int], timeout_s: int) -> dict:
    script = workdir / "experiments" / "fb-search" / "isolated" / "one_target.py"
    cases = []
    for n, count in targets.items():
        b = BASES[n]
        common = ["--n", str(n), "--family", b["family"], "--l", str(b["l"]), "--seed", str(b["seed"]),
                  "--mode", "ht", "--rerandomize", "walk", "--panel-key", PANEL_KEY]
        for index in range(count):
            tail = common + ["--index", str(index)]
            cases.append({"id": f"n{n}-target-{index}",
                          "reference": [str(python), str(script), "--variant", "rho"] + tail,
                          "candidate": [str(python), str(script), "--variant", "ic"] + tail})
    return {
        "schema": 1,
        "name": "ic-pdp2ht-vs-rho-one-target",
        "workdir": str(workdir),
        "isolation": {"cgroup": str(cgroup), "cpus": cpus, "execution_cpu": execution_cpu,
                      "mem_nodes": mem_nodes},
        "build": {"common": ["pdpkernel.c built by kernel.py (-O3 -march=native)", "CPython 3"],
                  "reference": "bench.rho_one_target (three-set r-adding walk, Floyd)",
                  "candidate": "monitor.collect --mode ht --rerandomize walk (PDP2ht, TDpdp walk)"},
        "candidates": {str(n): BASES[n]["candidate_id"] for n in targets},
        "artifacts": [str(workdir / p) for p in ARTIFACTS],
        "timeout_s": timeout_s,
        "repetitions": 1,
        "measurement_boundary": (
            "candidate online_ms: monitor.collect's per-target interval, from the first target rerandomization "
            "(walk step [a0]G) through the independent scalar replay [log Q]G == Q, every failed attempt "
            "included; factor base, relation collection, relation LA and log checks run before it and are "
            "excluded. reference online_ms: bench.rho_one_target from the first walk computation through "
            "scalar replay [s]G == Q. Fixture construction (s, Q = [s]G), interpreter start and imports are "
            "outside both. Both use the same ctypes field arithmetic; per-call overhead weighs more on rho."),
        "pair_fields": ["curve_id", "subgroup_order", "target_x", "target_y", "fixture_scalar", "panel_key",
                        "panel_index"],
        "cases": cases,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", type=Path, default=Path(sys.executable))
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--cgroup", type=Path, required=True)
    ap.add_argument("--cpus", required=True)
    ap.add_argument("--execution-cpu", type=int, required=True)
    ap.add_argument("--mem-nodes", required=True)
    ap.add_argument("--targets-19", type=int, default=64)
    ap.add_argument("--targets-23", type=int, default=32)
    ap.add_argument("--timeout-s", type=int, default=900)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if any(not p.is_absolute() for p in (args.python, args.workdir, args.cgroup, args.output)):
        ap.error("all paths must be absolute paths on the benchmark host")
    targets = {n: c for n, c in ((19, args.targets_19), (23, args.targets_23)) if c > 0}
    if not targets:
        ap.error("at least one target count must be positive")
    m = build(args.python, args.workdir, args.cgroup, args.cpus, args.execution_cpu, args.mem_nodes, targets,
              args.timeout_s)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(m, sort_keys=True, indent=2) + "\n")
    print(f"wrote {len(m['cases'])} frozen targets to {args.output}")


if __name__ == "__main__":
    main()
