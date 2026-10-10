# Exact prefix-support gate for the W15 six-pair challenge method

The exact W15 source counts identify the least demanding *prefix boundary* for the next
target-coupled decomposition kernel: fixing **one** of the two unconstrained
pairs leaves a five-pair suffix whose tuple count is at most
`4.3001132913835468e34`. For a uniform subgroup target, a fixed prefix
therefore has occupancy at most **6.31845×10⁻⁵**. At least **7,914 distinct,
target-independent prefix outputs** are necessary before the union-bound
success ceiling reaches one half. Within a 600-second online gate, those
probes and all target-dependent work would have to average at most
**75.815 ms per prefix**. This is a necessary resource gate, not a measured
five-pair query time or a success-rate estimate for the published point.

Fixing a constrained four-atom block first leaves an eight-atom suffix but
requires at least **130,559,879** prefix outputs at the same union-bound
threshold. Fixing both free pairs first requires at least
**4,277,789,264,560**. The calculation thus directs the next search toward
a compact **public-target five-pair membership and witness kernel**, with
one free pair as its outer prefix. The other partitions would require much
higher throughput under the same cap. These bounds do not constrain a method
that chooses prefixes jointly with the target.

## Exact model and bound

The exact field, curve, and subgroup are the degree-131 challenge instance
`EC1N131Ckb1heb5f1998f20b` with prime subgroup order
`r=680564733841876926932320129493409985129`. The audited W15 source has
**197,292** subgroup-usable factor-base points and **16,381** folded columns.
Its [seed-sum census](../n131_w15_coupled_sixpair_20261010/seed_sum_count.json)
gives `N=540,579,832` signed states for each unconstrained pair and
`M=8,918,874,017,088` signed states for each two-pair block whose mask-XOR
seeds agree. These counts exclude repeated columns *inside* each pair;
cross-pair column exclusions and collisions between group sums can only
reduce support. The full six-pair tuple ceiling is `N²M²`, whose group-wide
mean is **34,156.259** before those further exclusions.

For any fixed prefix group point independent of a uniformly selected target
`Q`, let the remaining tuple count be `C`. Its suffix sum set has at most
`C` group points, so `Pr[Q−prefix lies in the suffix set] ≤ min(1,C/r)`.
For `q` distinct target-independent prefixes, the union bound is at most
`min(1,qC/r)`; it needs `q ≥ ceil(r/(2C))` before this upper bound reaches
one half. No independence between prefix events is assumed. The input law
includes the subgroup identity; the supplied published challenge point is
fixed and must be tested by an actual query.

| Prefix frozen before the target join | Remaining tuple ceiling `C` | Occupancy upper bound | Necessary distinct prefixes `q` | Necessary average rate in 600 s |
| --- | ---: | ---: | ---: | ---: |
| One free pair | `N M²` | `6.31845×10⁻⁵` | **7,914** | 13.19/s |
| One constrained four-atom block | `N² M` | `3.82966×10⁻⁹` | **130,559,879** | 217,599.8/s |
| Both free pairs | `M²` | `1.16883×10⁻¹³` | **4,277,789,264,560** | 7.130×10⁹/s |

The [frozen protocol](protocol.json) binds both width-specific count
receipts and the integer calculator before evaluation. The
[calculation](result.json) retains exact rational occupancies, tuple counts,
prefix thresholds, and budget-per-probe fractions. An
[independent arithmetic audit](audit.json) re-derived each suffix by
dividing the full tuple census by its prefix multiplicity and checked the
minimality of every reported `q`. A second, separately
[frozen direct enumeration](direct_result.json) visited every unordered
pair of the 16,441 W15 source masks and independently reproduced
**135,144,958** accepted mask pairs, `N`, `M`, and the minimum and maximum
seed-bucket sizes without a Walsh transform. The W14 control at the same boundary
requires **2,027,316** one-free-pair prefixes, versus **7,914** for W15.
These are exact source-support and union-bound calculations; no CPU timing
ratio is asserted.

## Next constructive gate

Build a five-pair oracle that retains one unconstrained pair and both
same-seed four-atom blocks under the public target equation. Its N41
control must recover an unpinned ordinary relation, preserve all failed
prefix attempts, and independently replay the group sum and folded columns.
Then measure or source-bound *complete* N131 per-prefix work, including
proposal generation, all inverse calls, misses, branch and column checks,
and witness recovery. The first challenge-width attempt requires a frozen
one-worker 600-second / 4-GiB envelope and enough source-bound capacity to
test at least 7,914 distinct prefixes; the bound alone does not guarantee
that many prefixes succeed. Relation yield, rank novelty, factor-base logs,
fresh target recovery, and same-point rho remain the subsequent complete
IC gates. This support result is a design proposal with `candidate_id: null`.
