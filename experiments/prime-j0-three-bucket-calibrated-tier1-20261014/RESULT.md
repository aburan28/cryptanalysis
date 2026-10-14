# Calibrated RunPod scalar multiplication panel, initial allocation

The serial Tier 1 service ran the direct two-x norm-4831 reference and the
three-bucket candidate on two frozen secp256k1 scalar points. Both points and
every solver output replay against an independent scalar multiplication in
`verify_receipts.py`. The first case completed five alternating pairs with
five passing A/A calibration brackets. The second case crossed the frozen
5% calibration spread limit in two pairs, and the controller stopped before
submitting further cases. This preserves the failed observation and keeps the
five-point aggregate speedup unset.

| Fixture case | Job ID | Valid solve pairs | Passing A/A brackets | Median reference/candidate online ratio | Status |
| --- | --- | ---: | ---: | ---: | --- |
| 7 | `00df46d220fa4f5a923fcfb686584d82` | 5/5 | 5/5 | 0.866286 | completed stage |
| 8 | `049757e6d700437bb0feec72b7535776` | 3/5 | 3/5 | unset | invalid panel stage |

The allocation is RunPod pod `rrao2y0m5xlahr`, exposed CPU 14, NUMA node 0,
the same cgroup and 300-second cap for both arms, five repetitions per point,
and a 5% maximum A/A spread frozen in each manifest. The calibrator performs
the same 32 MiB SHA-256 workload four times around every pair. The archive
contains the allocation receipt, exact manifests, source files, source and
binary digests, preflight, solver and calibration stdout/stderr, raw run
timestamps and counters, pairs, summaries, and controller log. It contains
no pod credentials.

The raw archive is retained on the pod at
`/workspace/isolated-bench/calibrated-initial-panel.tar.gz` and in this
workspace at `/private/tmp/calibrated-initial-panel.tar.gz`. It is not in the
PR. Its SHA-256 is
`7a694647b00e100b17b553a1d905d66dc0e41cd07751fd7c16f63685da9d3f1e`.
Run `python3 verify_receipts.py /path/to/calibrated-initial-panel.tar.gz` to verify the archive
and independent scalar replays. The pod service remains available for new
serial jobs. A new speedup panel must use a fresh recorded allocation and
retain this failed panel, as required by `docs/IC_BENCHMARK_TIERS.md`.
