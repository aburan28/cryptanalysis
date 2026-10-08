# Batched affine wavefront for the unit-folded orbit graph

## Frozen question

Can breadth-first preparation of the existing unit-folded orbit graph reduce
the field work and complete preparation time for one newly supplied point?
The packed graph in PR #297 is the reference. This candidate keeps its exact
predecessor recipes, curve, subgroup, point table, online scalar recoder,
lookup layout, and scalar evaluation. It changes only how graph edges are
evaluated during point-dependent preparation.

The graph has depth at most three. Depth-one nodes are existing affine
positional digits. At each later depth, parent points from the previous
depth are affine. For every edge in that depth, form the affine addition
denominator, batch-invert all nonzero denominators with Montgomery's trick,
then finish the additions. Invert once per nonempty depth. Handle identity,
doubling, opposite points, and zero denominators explicitly. Preserve all
zero and small-order outcomes rather than assuming generic affine inputs.
Store exactly the same affine point for every orbit ID as the packed graph.

This combines known batched affine arithmetic with this graph's independent
depth layers. Batched affine addition itself is established prior art (for
example, [Barretenberg's implementation](https://barretenberg.aztec.network/api/classbb_1_1_batched_affine_addition));
this protocol makes no academic novelty claim.

## Frozen comparison and gates

Freeze this protocol in a draft stacked PR before native evaluation. Use the
eight public point/scalar cases in `orbit-graph-inputs.json`, without changing
their files or expected digests. Alternate packed-reference and wavefront
order. Compare all prepared affine table entries on each of the eight points,
then verify all 32,768 candidate scalar outputs against the independent
generic digests. Online additions, rotations, fallbacks, inversions, table
entries, and point-table bytes must match. Preparation graph additions and
unit rotations must match; report extra scratch bytes, batched denominators,
exceptional cases, and layer inversions separately. Retain raw failures and
hashes even if the candidate fails.

The depth histogram of the frozen graph predicts two batch inversions for
each width-10 or width-12 table and one for each width-8 table. Including the
common positional preparation inversion, that predicts nine preparation
inversions for either schedule, versus five and six for the packed reference.
The added inversions must be charged. Count any extra field operations used
to form or consume batch products; do not claim savings solely from point
addition counts. The point table remains 32 bytes per entry. Scratch and
resident memory must be reported explicitly.

The primary performance question is preparation of a newly supplied point,
followed by complete single-scalar latency and measured break-even target
count. A 4,096-scalar panel is a correctness and throughput diagnostic only;
its per-scalar average cannot answer the one-target question. Preserve setup,
online, and verification intervals separately. Promote a CPU timing claim
only with the physical host isolation receipt and noise gates in
`docs/ISOLATED_BENCHMARKS.md`. A RunPod container's affinity alone does not
establish exclusive host use. This algorithm is variable-time and intended
for public research scalars.

## Native diagnostic

The generic edge formula in the native candidate uses five field
multiplications and one squaring per nonexceptional edge, including the three
multiplications used to share the inverse. Doubling needs one additional
squaring. This model excludes positional-digit construction, unit rotations,
and the batch inversions; those remain separate counters. It also avoids the
reference builder's final projective-to-affine normalization pass. These are
source-level operation models, not measured CPU savings.

The [source-hashed panel](affine-wavefront-panel.json) passed all eight frozen
point/scalar cases. All 1,229,148 prepared affine entries across those points
matched the packed graph, and all 32,768 candidate outputs matched the
independent generic digests. Graph additions and unit rotations were equal
on every pair, with no fallbacks or exceptional additions on these two prime
subgroups. An additional order-13 curve test exercised exceptional edges on
both schedules and verified all 27 tested scalar outputs per schedule.
`test_curve` passed 2,260,204 checks.

| Schedule | Graph additions / batch denominators | Packed / wavefront inversions | Extra temporary heap | Candidate edge model |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 39,096 | 5 / 9 | 157,488 bytes | 195,480 M + 39,096 S |
| `j0-56` | 267,552 | 6 / 9 | 1,417,200 bytes | 1,337,760 M + 267,552 S |

The temporary heap figures describe simultaneously allocated scratch; the
unchanged affine point tables occupy 1,259,904 and 8,573,280 bytes. The
manifest for this candidate selects `prep_ms` with a per-point preparation
boundary. No physical host passed the isolation gate, so a preparation-time
speedup, complete one-scalar latency, break-even target count, and rho impact
remain unmeasured.
