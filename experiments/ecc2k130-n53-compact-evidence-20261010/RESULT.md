# Compact-orbit rank probes on the n41/n53 full-rank controls

The archived compact-orbit producer recovered the same held-out public point
with its paired signed-Frobenius rho run in all 24 source-curve comparison
arms. Replaying the pinned rank traces shows that the n53, K=220 base needs
18,413,613 support probes for 220 novel rank rows; its most expensive 22
searches consume 34.8261% of those probes. The six fresh-process timing
repeats at each base size have byte-identical rank traces. They measure timing
variation on one deterministic rank-query stream per arm, not six independent
rank-search streams. This is a **retrospective audit** of already published
data, not a new held-out comparison.

The exact input is `crypto` commit
[`de11f98ee53e63750596561f2b97fe84e41e50da`](https://github.com/aburan28/crypto/commit/de11f98ee53e63750596561f2b97fe84e41e50da),
whose [`HOLDOUT_ANALYSIS.json`](https://github.com/aburan28/crypto/blob/de11f98ee53e63750596561f2b97fe84e41e50da/experiments/koblitz-base-size-cold-panel-20261004/HOLDOUT_ANALYSIS.json)
hashes to `b54be182170a0986be1773e8e7a788cd380cc27c7dc8a3c4ea8ec4869acd8218`.
That analysis records executed producer source
`e37c50e9dbbc88148a12be648735894c37ba0b1a`. The original
[`RESULT.md`](https://github.com/aburan28/crypto/blob/de11f98ee53e63750596561f2b97fe84e41e50da/experiments/koblitz-base-size-cold-panel-20261004/RESULT.md)
and [PR #1353](https://github.com/aburan28/crypto/pull/1353) supply the
preregistered inputs, build and raw-file manifests, independent group/rank
replays, and resource receipts. The local [`audit.py`](audit.py) checks the
analysis hash, every rank-trace hash, all six repeat identities and rank
transitions, exact base size/digest, producer verification statuses and paired
IC/rho arithmetic. Its deterministic [`result.json`](result.json) retains
every derived count below.

Both panels use `y² + xy = x³ + 1` with no isogeny. Their exact curve IDs
are `EC1N41Ce0he09550ab560a` (subgroup order `549756390943`, generator
`[2056947637384,1635505394702]`) and `EC1N53Ce0hb097de99be9a`
(subgroup order `21044858204113`, generator
`[198217578752339,7929897206038174]`). The n53 polynomial basis is
`GF(2)[x]/(x^53 + x^6 + x^2 + x + 1)`; the exact field record for each curve
is in the pinned `crypto` source and base receipt. These producer diagnostics
retain `candidate_id: null` because complete `IC1` manifests were not
published for those cells. The held-out Q values are included in the table
artifact [`result.json`](result.json).

| Field / base | Actual usable B | Rank rows / failed attempts | Total probes | Median / p90 / max probes per row | Top decile probe share | Distinct rank streams / timing repeats |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| n41 / K85 | 6,970 | 85 / 0 | 2,100,243 | 16,482 / 59,303 / 135,996 | 36.2975% (9 rows) | 1 / 6 |
| n41 / K64 | 5,248 | 64 / 0 | 2,993,628 | 26,321 / 103,017 / 329,129 | 42.5301% (7 rows) | 1 / 6 |
| n53 / K220 | 23,320 | 220 / 0 | 18,413,613 | 52,493 / 198,997 / 865,863 | 34.8261% (22 rows) | 1 / 6 |
| n53 / K160 | 16,960 | 160 / 0 | 32,315,380 | 128,581 / 474,459 / 1,098,299 | 34.7410% (16 rows) | 1 / 6 |

All 529 listed rank attempts returned a group-verified relation and a novel
row in the archived traces. The audit's p90 is the nearest-rank order statistic;
the top decile comprises `ceil(K/10)` rows. The 24 full-run replay receipts
are independently verified in the original repository. The n53 baseline's
probe shares by **rank-order** quartile are 23.9686%, 24.2156%, 27.7321%
and 24.0837%, so this one stream has a heavy per-query tail without a
last-quartile concentration. These observations do not assign the tail to
particular columns or predict what a restart would cost.

| Field / base | IC / rho online median, ms | Paired median rho/IC online | IC / rho cold median, ms | Paired median IC/rho cold |
| --- | ---: | ---: | ---: | ---: |
| n41 / K85 | 2.631 / 13.409 | 5.106 | 480.211 / 13.659 | 35.144 |
| n41 / K64 | 3.320 / 13.913 | 4.255 | 572.210 / 14.194 | 40.049 |
| n53 / K220 | 6.736 / 135.913 | 19.300 | 5,586.337 / 136.538 | 40.365 |
| n53 / K160 | 11.767 / 155.319 | 13.899 | 9,418.334 / 155.784 | 57.965 |

These are six same-point, fresh-process pairs per arm on an unisolated macOS
host; the ratio columns are medians of pairwise ratios. Online IC starts
after reusable base/index/log preparation and includes target query, PDP,
relation check, descent and recovery check. Cold IC additionally charges base,
index, all full-rank work, matrix and final LA. Rho uses that arm's same
public Q and includes scalar replay. The n53 K220 and K160 arms have different
factor-base digests; their median **paired smaller/baseline IC cold ratio** is
1.635685, while total rank probes increase by 1.754972. This diagnoses the
fixed producer and base-size intervention; it is not a fixed-base algorithm
comparison or a controlled CPU speedup.

The older [signed-expanded n53 control](../ecc2k130-cold-fullrank-20261006/RESULT.md)
timed out at 180.342 seconds before publishing a target. Its base policy and
target differ from the compact-orbit controls, so a causal runtime ratio
between those producers remains unknown. The already merged [degree-263
transport](../koblitz-polynomial-w-pair-20260925/README.md) has a complete
exceptional-point replay, but this source-curve rank trace says nothing about
natural PDP yield or useful rank after that descent.

**Decision for the next producer experiment.** Keep n53 K220's exact 23,320
point base and public target fixed while testing whether a per-attempt probe
cap with a fresh deterministic scalar reduces the heavy rank-search tail.
The [next experiment protocol](NEXT_PROTOCOL.md) freezes its pilot caps and
requires independent rank seeds for the final comparison. It must count
aborted probes, new-query generation, final rank, target recovery and matched
rho, so a probe reduction alone cannot be reported as a cold or online gain.

Replay this audit from a clone containing the pinned `crypto` commit:

```sh
python3 experiments/ecc2k130-n53-compact-evidence-20261010/audit.py \
  --crypto-root /Volumes/SSD990/crypto \
  --out experiments/ecc2k130-n53-compact-evidence-20261010/result.json \
  --check
```
