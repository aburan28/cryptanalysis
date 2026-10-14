# N83 compact-orbit K899 third-target result: CPU-only control

**K899 reduced verified one-target online work by 8.05× relative to the
nested K800 base on a third frozen public point.** Its first verified target
relation took 76,705 probes, compared with 716,210 for K800. The K899 base
has 149,234 distinct usable subgroup points before sign/Frobenius folding
and 899 effective columns. Both candidates completed full rank and scalar
replay under the frozen 12 GiB sampled RSS cap. The full fresh-process cost
was 3.19× higher for K899 because its reusable root index and rank solution
took longer. This is a CPU-only secondary control on a shared Mac; its wall
ratios are exploratory and its controlled-speedup fields are null.

| Third public point, same source and resource cap | K800 | K899 |
| --- | ---: | ---: |
| Usable base points before folding | 132,800 | 149,234 |
| Effective signed-Frobenius columns | 800 | 899 |
| Regular index states | 53,120,000 | 67,080,683 |
| Distinct root-table entries | 53,117,564 | 67,077,932 |
| Index build | 121.099 s | 465.053 s |
| Guided rank | 89.793 s | 211.609 s |
| Rank / attempts / failed attempts | 800 / 800 / 0 | 899 / 899 / 0 |
| Mean probes per rank relation | 1,113,083 | 802,462 |
| Total rank probes | 890,466,092 | 721,413,364 |
| Target relation probes | 716,210 | 76,705 |
| Verified target online | 555.913 ms | **69.046 ms** |
| Full fresh-process wall | **212.858 s** | 678.149 s |
| Sampled peak RSS | 9,348,038,656 B | 8,986,804,224 B |

K899 is the largest size whose **source-level maximum** of `83*K²` regular
states keeps the current root table below its next power-of-two allocation
cliff. Its measured 67,080,683 states are just below the `2²⁸/4` threshold
of 67,108,864 states. The prior [K900 screen](../n83-compact-orbit-k900-20261012/README.md)
stopped at the same 12 GiB RSS cap while constructing its index. The smaller
sampled peak for K899 than K800 is a property of these two process samples;
it does not establish a general memory reduction.

The [frozen protocol](protocol.json) was committed and pushed before the
run at `7b7f66add`. It fixes the new public point, source commit
`6600c7c6c0cfbb6a9e4e596bf8c5cfa292fb269e`, base-construction rule,
rank seed 29, 12 rank threads, one target thread, tuned same-point rho,
arm order, 60-minute IC process cap, 60-second rho cap, and 12 GiB sampled
RSS stop. The public point is in [`target.jsonl`](target.jsonl); its fixture
scalar is confined to the [validation sidecar](validation_sidecar.json),
outside both worker inputs. The exact source and executable hashes are
retained in the protocol and [binary manifest](binary_manifest.json). The
clean-source [rebuild receipt](../n83-compact-orbit-k900-20261012/build_provenance.json)
independently reproduced both executed binary hashes on this host.

The [independent target verifier](verification.json) passed every input,
binary, phase-sum, rank, base-nesting, four-point relation, scalar replay,
and paired-rho charge check. The [full K899 base replay](full_base_replay.json)
checked every point and label, all 899 representatives in the prime-order
subgroup, 166-point orbit closure, and distinct orbit keys. K800's repeated
base dump is byte-identical to the earlier archived K800 dump. The
[factor-base archive](../fb-archive/README.md#n83-a1-compact-orbit-bases)
retains the exact K899 point set by digest. The [canonical measurement rows](measurements.json)
record the five exclusive target-online phases, full process costs, full
curve/candidate UIDs, archive and replay links, and null controlled speedups.
The [hardware audit](hardware.json) binds all four arm receipts, records
`gpu.devices: []`, and leaves unavailable affinity, page-placement and
co-runner counters null.

The tuned strong-rho reference solved this exact point before and after the
IC arms in 3,166.133 and 3,611.350 ms online. Both rho runs had the same
13,112,129-step walk and identical charge records. The verified IC online
interval starts after target-independent base, index, rank, and factor-log
preparation, then charges target query, PDP, relation check, direct descent,
and scalar replay. Full fresh-process time includes that preparation and is
reported separately.

To replay the read-only checks from a checkout with the pinned clean crypto
source available as `N83_CRYPTO_REPO`:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-6600c7c6 python3 experiments/n83-compact-orbit-k899-20261012/verify.py
N83_CRYPTO_REPO=/path/to/crypto-at-6600c7c6 python3 experiments/n83-compact-orbit-k899-20261012/verify_full_bases.py --verify-only
python3 experiments/n83-compact-orbit-k899-20261012/verify_identities.py
python3 experiments/fb-archive/compact_orbit_base_archive.py --verify-only
```

This result makes K899 the stronger completed target-online candidate on the
third point within the current index representation and 12 GiB cap. A
held-out point panel is needed to estimate first-witness variability, and a
CUDA-host run with a Tier 1 or Tier 0 CPU timing receipt is needed to qualify
a wall-time speedup. A packed root-table implementation could test bases
above this allocation boundary without the current 16 GiB table jump.
