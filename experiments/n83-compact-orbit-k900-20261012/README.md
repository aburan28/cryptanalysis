# N83 compact-orbit factor-base capacity screen: CPU-only control

**K800 completed a second verified one-target run; K900 crossed the frozen
12 GiB RSS cap during root-index construction.** The K800 base dump is byte
identical to the prior K800 base, and its candidate identity remains
`IC1N83Ckb1a1fb132800PDP4rootRCguidedLAgaussTDdirectISO0h97f37aa0f6fd`.
The second public target has workload ID `dba72e7f8c63`. The K900 arm is a
resource-censored attempt with a null target-online result and null candidate
ID. The completed-candidate comparison is therefore censored at K900.

| Second frozen public target, local Mac CPU-only secondary control | K800 | K900 |
| --- | ---: | ---: |
| Actual usable base points before folding | 132,800 | null; base dump absent |
| Effective signed-Frobenius columns | 800 | planned 900 |
| Regular index states | 53,120,000 | null; index stopped |
| Distinct root-table entries | 53,117,564 | null |
| Index build | 365.156 s | capped before completion |
| Guided rank | 356.476 s; 800/800 relations | not reached |
| Target relation probes | 261,114 | null |
| Verified single-target online | 360.598 ms | null |
| Fresh-process wall | 723.347 s | 2,133.383 s to RSS stop |
| Sampled peak RSS | 9,521,709,056 B | 13,020,676,096 B |
| Disposition | verified exit | `rss_cap`, exit −15 |

The cap was 12,884,901,888 B. The raw [K900 execution receipt](runs/K900/execution.json)
records the stop and hashes its empty target output and raw stdout/stderr.
The independent [verification receipt](verification.json) accepts this as
`CENSORED_CAP`, while checking the completed K800 scalar and four-point
relation with a separate Python field implementation. The K800 base matches
the [previous full-base replay](../n83-compact-orbit-size-sweep-20261012/full_base_replay.json)
byte for byte. The [canonical records](measurements.json) include K800's five
exclusive target-online phases. [`censored_K900.json`](censored_K900.json)
retains null candidate and online fields and binds the raw cap receipt.
The [hardware and execution audit](hardware.json) binds every arm receipt to
the Apple M4 Pro host and explicitly records unpinned CPU placement, unknown
page placement and co-runners, and `gpu.devices: []`. It was collected after
the run, so dynamic host counters that were not retained at execution remain
null. This CPU-only control does not satisfy the repository's CUDA-host gate
for primary IC measurements.

The same tuned strong-rho reference solved this exact public point before and
after the IC arms in 1,988.326 and 2,743.458 ms online. Both rho executions
had the same 5,746,446-step walk and identical charge records. Their wall
variation and the shared host make local timing ratios exploratory; the
controlled-speedup field remains null. The full fresh-process cost is kept
separate from target-online time, which begins after the reusable index and
factor-base logs are ready.
The full [curve UID and candidate UID bindings](identity_bindings.json) use
the unchanged canonical field, curve, and candidate preimages; the K800 row
also retains the full UIDs. The K800 point-set digest is in the
[factor-base archive](../fb-archive/README.md#n83-a1-compact-orbit-bases)
alongside the earlier K600 set, with all points and the independent replay
hashes retained in Git chunks.

## Why K899 is the next size

In the pinned `crypto` source, `build_index128` visits at most `83*K*K`
ordered pair/relative-rotation states. `RootTable128::with_capacity` requests
the next power of two above four times the actual state count, and each
`(u128,u64)` table slot is 32 bytes on this target. K800 reported exactly
`83*800² = 53,120,000` regular states. At K899, even the source-level maximum
requests `4*83*899² = 268,322,732` slots, below `2²⁸ = 268,435,456`; its
table allocation is therefore at most 8 GiB. At K900 the corresponding
maximum is `268,920,000`, above the boundary, so a near-maximal state count
requests `2²⁹` slots, or 16 GiB for the table alone. The K900 cap is
consistent with that allocation jump. K899's total process RSS and target
performance still require a measured run.

[`CapacityBound.lean`](CapacityBound.lean) checks the two numeric inequalities
and 8 GiB slot arithmetic under Lean 4 v4.34.1. The proof map is:

| Result | Lean declaration | Exact scope |
| --- | --- | --- |
| K899 request fits at most `2²⁸` slots | `N83CompactOrbitCapacity.k899_requested_slots_fit` | conditional on `states ≤ 83*899²` |
| K900 maximal request crosses `2²⁸` | `N83CompactOrbitCapacity.k900_maximum_crosses_boundary` | numeric maximum; does not assert all states exist |
| `2²⁸` slots at 32 B use 8 GiB | `N83CompactOrbitCapacity.table_slot_bytes_at_boundary` | arithmetic only |

The Rust loop bound, `next_power_of_two` call, and slot layout are source and
compiled-layout checks, not Lean definitions. The [Lean build and axiom
audit](proof_check.json) retains the exact command, toolchain, stdout, source
hash, and core foundations; all three declarations report no axioms.
`lean4checker` was unavailable. The [compiled slot-layout receipt](slot_layout_receipt.json)
retains the exact-target Rust `size_of::<(u128,u64)>() = 32` check and compiler
version. The source is the clean public `crypto` commit
`6600c7c6c0cfbb6a9e4e596bf8c5cfa292fb269e`; exact source and binary
hashes, run order, one public input, seeds, 12 rank threads, one target thread,
40-minute IC cap, 60-second rho cap, and RSS cap are in the
[frozen protocol](protocol.json), [binary manifest](binary_manifest.json),
and [run receipts](runs/). The public target is in [`target.jsonl`](target.jsonl);
its fixture scalar was held in a validation sidecar outside both worker inputs.
The [post-run independent build audit](build_provenance.json) recompiled the
clean pinned source and compared both executable hashes with the recorded
ones. The original launcher checked the commit and source-file hashes; the
current launcher also requires a clean tree and an offline Cargo build before
future execution. The post-run audit is identified as such in its receipt.

Replay the checks against the pinned clean source checkout:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-6600c7c6 python3 experiments/n83-compact-orbit-k900-20261012/verify.py
python3 experiments/n83-compact-orbit-k900-20261012/verify_identities.py
(cd experiments/n83-compact-orbit-k900-20261012 && lean CapacityBound.lean)
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
```

This run identifies K800 as the largest completed candidate in the current
12 GiB screen. The next frozen one-target comparison should test K899 on a
new public point, retaining K800 as the same-point control. A held-out point
panel and a Tier 1 cloud-instance or Tier 0 host receipt are then needed to
judge target-probe variation and qualified wall-time speedup.
