# Two-fixed-pair completion density bound and exact N41 census

**Contribution.** For the frozen N131 same-rotation W18 geometry, a schedule
that fixes two pair outputs independently of a uniformly selected nonidentity
target needs at least **286,174,705,817,677,085** exact completion probes
for a 50% success probability, even if each probe has zero cost. This is a
conditional union bound on the search schedule. The accompanying exhaustive
N41 census measures the two-free-pair completion support and every
admissible prefix on the fixed public point.

## Bound

Let `D2` and `D3` be the exact pair-output domains, and let a chosen first-two
pair prefix leave residual `R=Q-U0-U1`. For a target `Q` uniform among the
`r-1` nonidentity subgroup points, a prefix chosen without target-coordinate
information has a uniformly translated residual. One designated W18 slot has
262,614 signed usable points, so each pair domain has at most
`M=C(262614,2)=34,482,925,191` outputs before folded-column exclusions or
collisions. Therefore `|D2+D3| <= M^2` and a predeclared schedule of `L`
prefixes obeys

`Pr[at least one completion] <= min(1, L*M^2/(r-1))`,

where `r=680564733841876926932320129493409985129`. The single-prefix upper
probability is `1.747184464019513... × 10^-18`. Reaching 50% by this bound
requires `L >= 286174705817677085`, or more than
`4.76957843029461 × 10^14` probes per second in 600 seconds. Exact fractions
and ceiling arithmetic are retained in [bound.json](bound.json); the
[independent audit](verification.json) recomputes them from the earlier
frozen W18 factor-base count.

The bound applies to target-independent prefix sequences, including a
sequence that follows the all-miss path of an exact completion oracle. A
method that uses `Q` to generate correlated prefixes or eliminates prefix
families algebraically has a different input law; this theorem does not
assign its success probability.

## Exhaustive N41 experiment

The [frozen protocol](protocol.json) uses the same-rotation W6 public point
`Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0`, subgroup order `549756390943`. Four pair domains
have 1,956 exact signed, distinct-column pair witnesses each. The
[native census](n41_census.json) enumerates all sums of domains 2 and 3,
sorts their encoded group points, and checks every admissible residual from
domains 0 and 1. The source and binary were [frozen](freeze.json) before the
run; its 120-second query cap and 4-GiB memory cap were not reached.

| Exact N41 quantity | Result |
| --- | ---: |
| Raw `D2 × D3` combinations | 3,825,936 |
| Distinct completion points | **3,825,936** |
| Admissible first-two-pair prefixes after four-column check | 3,167,136 |
| Exact completion-set hits for the fixed public point | 20 |
| Rows with eight distinct folded columns | 12 |
| First completion hit / first eight-column row, admissible-prefix index | 155,013 / 513,088 |
| Completion-set build / fixed-point query wall time | 1.838 s / 7.803 s |
| Peak RSS | 62,783,488 bytes |

The N41 completion map is injective on all 1,956-by-1,956 pair-witness
combinations in this frozen geometry. Its exact support fraction for a
uniform nonidentity residual is `3,825,936/(549,756,390,942)`, about
`6.95933 × 10^-6`. The fixed public point gives 20 hits among 3,167,136
admissible prefixes, about `6.31485 × 10^-6`; this is a full census of that
point, so there is no sampling interval for the reported count.

The first accepted row and its index match the earlier
[Q1448 public-target result](../q1448_pair_bloom/result.json), whose
[installed-Sage audit](../q1448_pair_bloom/sage_audit_v2.json) independently
replayed the points, columns, subgroup membership, and group sum. The 12
accepted rows match the earlier complete twelve-row census count. The prior
batch-inversion search stopped after 75,264 admissible prefixes, before the
first completion hit measured here. Native CPU times are exploratory because
this host has no isolation receipt; the exact cardinalities and conditional
bound do not depend on those times.

## Research consequence and next test

Making the two-free-pair oracle faster changes the cost of a probe but does
not change the `2.86 × 10^17` probe requirement under the target-independent
schedule. The next constructive test must use the target to select first-pair
families or eliminate them jointly. A specific small gate is to ask whether
the x and y coordinates of a valid two-pair sum expose either pair's seed-sum
mask through a compact algebraic decoder. An exact decoder could feed the
existing implicit W18 pair-membership circuits without storing the full pair
domains. A rank witness on valid sums can eliminate a declared low-degree
decoder family before a larger SAT or resultant experiment.

The result is an IC method diagnostic under proposal `Q20261008220700`;
candidate and run IDs remain null. Its claim boundary is the target law and
prefix schedule stated above, with the exact N41 factor-base and public
point specified in the protocol.

## Reproduction

From the repository root, compile `census.cpp` with the command in
`freeze.json` and run its frozen input/output command. `bound.py` derives the
exact fractions from the saved census and W18 frontier; `verify.py` checks
the hashes, independent arithmetic, prior Sage row audit, and census
invariants. The first-run producers refuse to overwrite retained receipts.
