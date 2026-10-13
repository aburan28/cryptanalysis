# N83 packed-root finalists: K1271 wins the frozen 256-point probe decision

**K1271 had the lower paired mean target-probe count on 256 new public N83 points under one 16 GiB sampled RSS cap.** It averaged 356,856 probes versus 434,061 for K1200, a difference of 77,205 probes per point. The frozen 10,000-resample paired bootstrap interval for K1200 minus K1271 is 8,369 to 145,803 probes, entirely above zero, so the [predeclared decision rule](protocol.json) selects K1271. All 512 target answers and four-point relations passed independent replay.

| Frozen finalist workload | K1200 | K1271 |
| --- | ---: | ---: |
| Actual usable points before folding | 199,200 | **210,986** |
| Effective columns | 1,200 | 1,271 |
| Verified public targets | 256/256 | 256/256 |
| Mean target probes | 434,061 | **356,856** |
| Median target probes | 288,738 | **249,002** |
| 90th-percentile target probes | 1,048,858 | **843,844** |
| Maximum target probes | 2,283,722 | **1,884,978** |
| Mean online ms, exploratory | 197.254 | **150.915** |
| Fresh-process wall s | 220.739 | **216.367** |
| Sampled peak RSS B | 14,365,392,896 | 11,078,320,128 |

K1271 used fewer probes on 136 points and K1200 on 120. The [analysis](analysis.json) retains exact per-arm statistics, the paired mean and median differences, bootstrap seed `20261013256`, the 10,000-resample percentile result, and the frozen decision. The mean-probe ratio from these measurements is `434060.75390625 / 356856.01171875 = 1.2163`. The measured online mean ratio is `197.25440854296875 / 150.91502019140626 = 1.3071` on a shared Mac CPU and remains exploratory. Probe counts are deterministic stage diagnostics; the comparison is not a one-target speedup or a host-isolated timing claim.

This **secondary shared-preparation** study followed completed one-target measurements and two 32-point screens. Each arm built a fresh factor base and packed root index, solved its factor-log system, and then processed the identical 256 public points sequentially. The setup and full-process costs are separate from every target's five exclusive online phases. The one-target matched-rho measurements remain in the earlier [capacity result](../n83-packed-root-capacity-20261013/README.md). K1271's selection here is over the two finalists under the specified source and resource envelope; [the seven-base screen](../n83-packed-root-panel-16g-20261013/README.md) records the broader K800–K1271 comparison.

The [protocol](protocol.json), public [target list](targets.jsonl), and [validation sidecar](validation_sidecar.json) were committed and pushed before execution at `0211f45ac`. The producer received only points. The protocol fixes source commit `4794b94c945fce142292ef69ae48e5f88d267f44`, rank seed 29, 12 rank threads, one target thread, packed `u128` slots, arm order, 60-minute process limit, 16 GiB sampled RSS stop, target-generation law, and bootstrap decision rule. The [runner](run.py) checks the source, lockfile, and input hashes and builds offline. Its executable hash matches the earlier [independent clean-source rebuild](../n83-packed-root-capacity-20261013/build_provenance.json).

The [raw arm receipts](runs/) retain all 512 target rows, exact base dumps, hashes, exit states, phase times, full process wall, and sampled RSS. The [independent verifier](verification.json) reports `PASS` with zero failing checks: scalar and four-point group replay, phase sums, complete rank, packed layout, nested bases, and byte-identical dumps against the earlier [fully replayed factor-base archives](../fb-archive/README.md#n83-a1-compact-orbit-bases). Both arms use curve `EC1N83Ckb1a1haacb69ee9f37` and workload `67ccbdd2301e`. [Canonical run records](measurements.json) retain each IC1 candidate ID, actual point count, per-target phases, shared preparation, and null controlled-speedup fields. [Identity replay](verify_identities.py) checks curve, candidate, workload, run, hardware, archive, and raw target bindings. The [hardware audit](hardware.json) labels the CPU-only shared host and records unavailable isolation counters as null.

K1271 is the selected prefix base among the tested K1200/K1271 finalists for mean online probe work. The next factor-base experiment is an opt-in denser root table that could admit more than 1,271 columns within the current index allocation, followed by fresh matched target measurements.

Read-only replay from a checkout with the pinned clean crypto source:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-4794b94c python3 experiments/n83-packed-root-finalists-20261013/verify.py
python3 experiments/n83-packed-root-finalists-20261013/verify_identities.py
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
```
