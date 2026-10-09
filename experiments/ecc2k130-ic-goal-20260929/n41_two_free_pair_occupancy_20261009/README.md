# Exact two-free-pair occupancy and fixed-prefix completion bounds

**The frozen N41 four-pair policy has 3,167,136 distinct two-free-pair group
sums, and the supplied public target has 12 complete eight-column rows.**
An independent installed-Sage implementation recounted every suffix sum and
every target residual and replayed all 12 rows. This establishes the exact
completion occupancy that a compact target-coupled propagator must recognize
on this positive smaller-field control.

The [protocol](protocol.json) fixes `EC1N41Ckb1h7d5e80d3c4d0`, the public
point `Q=(1458168294740,1672312028033)`, four same-rotation W6 pair
domains at rotations `0,10,20,30`, 1,956 valid two-point states per domain,
and distinct folded columns across each eight-point row. The producer
loads no scalar or known row. Its target-independent setup builds an exact
index of the last two pair domains; the target-dependent interval checks
every valid first-two-pair prefix against the public residual. This
quadratic index is a measurement reference for the missing compact
propagator, with all 4-GiB and 600-second diagnostic limits frozen before
execution.

| Exact N41 observation | Count |
| --- | ---: |
| Valid assignments in the last two pair domains | 3,167,136 |
| Distinct last-two-pair group sums | 3,167,136 |
| Valid first-two-pair prefixes | 3,167,136 |
| Prefix residuals in the suffix support | 19 |
| Complete relations with eight distinct folded columns | 12 |

The suffix support occupies exactly `3,167,136 / 549,756,390,943`, or
`5.761×10⁻⁶`, of the prime subgroup. A uniformly sampled independent target
would give 18.246 support hits in expectation across this many fixed
prefixes; the supplied point gives 19, of which 12 pass the cross-pair
column filter. The [producer result](result.json) retains the 12 complete
point-index witnesses, exact counts, phase times, input hashes, and resource
peak. The [independent Sage audit](audit.json) rebuilds all four domains
from the frozen geometry, recounts all 3,167,136 suffix assignments and all
3,167,136 public-target prefixes, checks the N131 arithmetic bound, and
replays every saved group sum and column set. It returned
`PASS_FULL_EXACT_RECOUNT_AND_GROUP_REPLAY`.

The earlier [compact two-free-pair lookup](../n41_two_free_pair_compact_lookup_20261009/RESULT.md)
counts all `1,956² = 3,825,936` last-two-pair assignments before checking
whether the two pairs reuse a folded column. This census applies that
cross-pair column condition when building the suffix support, leaving
3,167,136 assignments. The counts therefore measure different, explicit
support policies. The earlier target-conditioned lookup already found an
ordinary row in 32.222 seconds with its exact-table reference and passed
checked-Sage replay. Its literal N131 W18 transfer requires more than
4 GiB for even one bit per pair state, before group coordinates or indexes;
an implicit representation remains the missing method component.

| Local diagnostic stage | Wall (s) | Process peak RSS |
| --- | ---: | ---: |
| Target-independent suffix index and pair setup | 180.516 | — |
| Supplied-Q prefix scan | 173.704 | — |
| Complete producer execution | 354.219 | 616,890,368 B |
| Independent full Sage recount | 157.182 | 1,637,761,024 B |

These wall times are exploratory because the host lacks an isolation
receipt. The counts and group equations are exact. The reference query
exceeds the 120-second N41 constructive gate and materializes a quadratic
suffix index. Its purpose is an exact filtered completion oracle for a
method that can also pass the N131 work and memory projection.

The same source-bound union-bound calculation quantifies the N131
fixed-prefix frontier for two distinct policies. The frozen W18 four-pair
[geometry snapshot](geometry_snapshot.json) has at most
`C(262,614,2)=34,482,925,191` states per pair before column filtering.
For a target uniform over nonidentity subgroup points and independent of
each fixed two-pair prefix, the two remaining pair domains have completion
probability at most `1.747185×10⁻¹⁸` per prefix. At least
`286,174,705,817,677,085` fixed-prefix probes are necessary for 50%
success by the union bound, or more than `4.769×10¹⁴` probes per second in
600 seconds. The exact integer fraction and arithmetic are in
[result.json](result.json).

For the current d13 six-pair policy, the independently audited
[pair inverse](../n131_d13_same_rotation_pairs_20261009/RESULT.md) counts
8,542,911 unordered distinct-selector pairs. Four sign choices give at
most 34,171,644 group-output descriptors per pair. After four pair
outputs are fixed independently of a uniform nonidentity target, the last
two pairs have completion probability at most `1.715783×10⁻²⁴`.
[The source-bound calculation](d13_fixed_prefix_bound.json) requires at
least `291,412,179,145,627,003,543,092` fixed four-pair prefixes for 50%
success by the union bound, more than `4.857×10²⁰` probes per second under
the 600-second budget. This independently agrees with the
[full d13 prefix frontier](../n131_d13_six_pair_prefix_frontier_20261009/RESULT.md),
which also quantifies the four-free-pair case after two fixed pairs. The
result here binds snapshots of both the exact pair count and the candidate
curve/subgroup manifest.

These bounds apply to fixed prefixes chosen independently of the uniform
target. They leave target-adaptive generation and symbolic elimination
open. A successor should preserve the existing N41 ordinary-row control
while using the public target to reject whole partial pair families before
materializing large pair-state vectors. Its N131 work projection must
charge that generation or elimination; accelerating only the final pair
membership check cannot overcome the fixed-prefix density frontier.

All result files are write-once. To reproduce the diagnostic with the
frozen inputs and accepted Sage runtime, run `./sage -python` on
[`run.py`](run.py), then [`audit.py`](audit.py). The posthoc d13 bound is
produced by [`transfer_bound.py`](transfer_bound.py). Each script refuses
to overwrite its existing result; copy the frozen source directory to a
new experiment location before an independent rerun.
