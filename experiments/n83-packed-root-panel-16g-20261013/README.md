# N83 packed-root panel: K1271 has the lowest mean probes across seven bases

**All seven nested N83 bases completed 32 new public targets under one 16 GiB sampled RSS cap.** K1271, with 210,986 actual usable subgroup points and 1,271 folded columns, had the lowest observed arithmetic mean of 457,471 target probes. K1200 had the lowest median at 137,895 probes. K1271's mean online interval was 213.794 ms on the shared Mac CPU; these wall measurements are exploratory.

| Base | Actual usable points | Folded columns | Mean probes | Median probes | Mean online ms, exploratory | Fresh process s | Sampled RSS B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| K800 | 132,800 | 800 | 1,204,200 | 1,156,774 | 482.381 | **121.112** | 6,883,688,448 |
| K899 | 149,234 | 899 | 658,967 | 397,783 | 328.572 | 144.372 | 7,552,483,328 |
| K900 | 149,400 | 900 | 621,286 | 519,558 | 319.180 | 149.927 | 9,525,133,312 |
| K1000 | 166,000 | 1000 | 554,398 | 429,392 | 239.058 | 151.546 | 12,610,633,728 |
| K1100 | 182,600 | 1100 | 622,690 | 432,619 | 274.945 | 161.896 | 10,216,603,648 |
| K1200 | 199,200 | 1200 | 521,948 | **137,895** | 272.652 | 188.958 | 10,242,048,000 |
| K1271 | **210,986** | 1271 | **457,471** | 297,042 | **213.794** | 222.299 | 12,440,600,576 |

The [analysis](analysis.json) reports all 32 per-point costs, 90th percentiles, maxima, pointwise wins, and paired target-resampling intervals. K1271's mean-probe difference from K1200 is 64,477 probes in this panel; the descriptive 95% paired bootstrap interval for K1200 minus K1271 spans -251,552 to 456,986. The observed lead is therefore unresolved at that uncertainty level. Across the 64 different points in the first 12 GiB and this 16 GiB panel, [pooled probe analysis](pooled_probe_analysis.json) puts K1271 at 390,999 mean probes and K1200 at 523,055; its stratified paired interval for K1200 minus K1271 spans -66,503 to 364,097. The pooled analysis uses deterministic probe counts only and keeps the different caps visible.

This is a **secondary shared-preparation workload**. Each fresh arm builds one base, one packed root index, and its factor-log solution, then processes the same 32 public points in sequence. The default one-target online and matched-rho measurements are in the earlier [capacity result](../n83-packed-root-capacity-20261013/README.md). No multi-target average is used as a one-target speedup. The 16 GiB cap resolved K1000 and K1100, which had [resource-censored 12 GiB rows](../n83-packed-root-panel-20261013/README.md); both completed every new point here.

The [protocol](protocol.json), public [target list](targets.jsonl), and [validation sidecar](validation_sidecar.json) were committed and pushed before execution at `9a20f8800`. The producer received only the point list. The protocol fixes source commit `4794b94c945fce142292ef69ae48e5f88d267f44`, rank seed 29, 12 rank threads, one target thread, packed `u128` slots, arm order, 60-minute process limit, 16 GiB sampled RSS stop, and the input law. The [runner](run.py) verifies source, lockfile, and input hashes before building offline. Its executable hash matches the earlier [independent clean-source rebuild](../n83-packed-root-capacity-20261013/build_provenance.json).

The [raw arm receipts](runs/) retain all target rows, base dumps, source and binary hashes, output hashes, process dispositions, wall time, and sampled RSS. The [independent verifier](verification.json) reports `PASS` with zero failing checks: 224 scalar and four-point group replays, phase sums, full rank, packed layout, nested bases, and byte-identical repeats for the five previously archived bases. The [new full-base replay](full_base_replay.json) checks all 166,000 K1000 and 182,600 K1100 point/label rows, subgroup representatives, signed Frobenius orbit closure, and distinct orbit keys. Both exact sets are in the [factor-base archive](../fb-archive/README.md#n83-a1-compact-orbit-bases), whose verify-only check passes.

All seven use curve `EC1N83Ckb1a1haacb69ee9f37` and workload `a63619bbe84d`. [Canonical run records](measurements.json) retain each IC1 candidate ID, actual pre-fold count, five exclusive per-target online phases, shared preparation, and null controlled-speedup fields. [Identity replay](verify_identities.py) checks curve, candidate, workload, run, hardware, archive, and raw target bindings. The [hardware audit](hardware.json) records CPU-only shared-host placement and unavailable isolation counters as null.

K1271 is the best observed base by the predeclared mean-probe metric among these seven under this cap. A larger fresh paired point sample for K1200 and K1271 can resolve their close ranking. An opt-in denser root table is the next implementation experiment for testing larger bases within the same table allocation.

Read-only replay from a checkout with the pinned clean crypto source:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-4794b94c python3 experiments/n83-packed-root-panel-16g-20261013/verify_full_bases.py --verify-only
N83_CRYPTO_REPO=/path/to/crypto-at-4794b94c python3 experiments/n83-packed-root-panel-16g-20261013/verify.py
python3 experiments/n83-packed-root-panel-16g-20261013/verify_identities.py
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
```
