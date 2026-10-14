# N83 packed-root panel: K1271 leads five completed bases across 32 points

**K1271 required the fewest target probes among the five bases that completed the frozen 12 GiB panel.** Across 32 new public points it averaged 324,528 probes, with median 149,485. K800 averaged 1,241,582 probes on those same points, a 3.83-fold observed probe ratio. K1271's observed online mean was 160.726 ms versus K800's 514.701 ms. CPU wall times came from a shared Mac and remain exploratory. The two intervening arms K1000 and K1100 hit the sampled RSS cap before producing target rows; their target costs are censored.

| Base | Actual usable points | Folded columns | Mean probes | Median probes | Mean online ms, exploratory | Fresh process s | Sampled RSS B | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| K800 | 132,800 | 800 | 1,241,582 | 768,273 | 514.701 | 143.735 | 6,885,261,312 | 32/32 verified |
| K899 | 149,234 | 899 | 783,183 | 573,386 | 311.431 | **116.608** | 7,557,070,848 | 32/32 verified |
| K900 | 149,400 | 900 | 686,871 | 347,240 | 286.233 | 131.427 | 11,852,234,752 | 32/32 verified |
| K1000 | unknown from this run | 1000 planned | unknown | unknown | unknown | 85.271 to cap | 12,903,596,032 | RSS cap, exit -15 |
| K1100 | unknown from this run | 1100 planned | unknown | unknown | unknown | 42.404 to cap | 13,297,958,912 | RSS cap, exit -15 |
| K1200 | 199,200 | 1200 | 524,163 | 365,018 | 235.292 | 179.534 | 12,820,332,544 | 32/32 verified |
| K1271 | **210,986** | 1271 | **324,528** | **149,485** | **160.726** | 189.549 | 12,112,871,424 | 32/32 verified |

The [analysis](analysis.json) contains exact means, medians, 90th percentiles, maxima, per-point win counts, and 10,000-resample paired bootstrap intervals. K1271 won 13 of 32 pointwise probe comparisons; K900 won 10. The observed paired mean-probe difference K900 minus K1271 was 362,344, with a descriptive 95% bootstrap interval of 76,340 to 675,137. The interval was computed after selecting K1271 from this panel, so it is a descriptive uncertainty measure rather than a selection-adjusted test.

This is a **secondary shared-preparation workload**. Each arm constructs its base and packed index, solves its factor-base log system, then processes the same 32 public points sequentially. The default single-target online comparisons and matched rho receipts remain in the earlier [K900 capacity result](../n83-packed-root-capacity-20261013/README.md). The panel compares factor-base sizes on paired points under a fixed cap; it does not use a multi-target average as the one-target speedup metric. A fresh-process wall figure charges shared setup once for the 32 points and is not the one-target online interval.

The [protocol](protocol.json) and public [target list](targets.jsonl) were committed and pushed before execution at `037ecf0cd`. The fixture scalars stayed in the [validation sidecar](validation_sidecar.json), outside the producer input. The protocol fixes source commit `4794b94c945fce142292ef69ae48e5f88d267f44`, rank seed 29, 12 rank threads, one target thread, packed `u128` slots, seven-arm order, 60-minute process limit, 12 GiB sampled RSS cap, and the 32-point input law. Its source and input hashes are checked by the [runner](run.py).

The [raw arm receipts](runs/) retain stdout, stderr, the target rows produced before exit, base dumps where available, execution dispositions, caps, hashes, wall time, and sampled peak RSS. The [independent verifier](verification.json) reports `CENSORED` for the entire seven-arm panel with zero failing integrity checks. It replayed all 160 recovered scalars and four-point group sums from the five complete arms, checked phase sums, full rank, packed layout, nested bases, and byte-identical base dumps against previously [fully replayed exact archives](../fb-archive/README.md#n83-a1-compact-orbit-bases). The two capped arms have no inferred target yield. The executed IC binary hash matches the prior [independent clean-source rebuild](../n83-packed-root-capacity-20261013/build_provenance.json) for the same source commit.

All complete arms use curve `EC1N83Ckb1a1haacb69ee9f37` and panel workload `37f11d3cacec`. Their [canonical run records](measurements.json) retain IC1 candidate IDs, actual pre-fold point counts, five per-target online phases, shared preparation, and null controlled-speedup fields. [Identity replay](verify_identities.py) checks curve, candidate, workload, run, hardware, exact factor-base archive, and raw target bindings. The [hardware audit](hardware.json) records CPU-only shared-host placement and unavailable isolation counters as null.

K1271 is the best observed base among the five completed arms for the panel's predeclared mean-probe selection metric. A 16 GiB same-cap follow-up across all seven sizes is the next step to resolve the two censored sizes and assess whether the ordering persists on new points.

Read-only replay from a checkout with the pinned clean crypto source:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-4794b94c python3 experiments/n83-packed-root-panel-20261013/verify.py
python3 experiments/n83-packed-root-panel-20261013/verify_identities.py
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
```
