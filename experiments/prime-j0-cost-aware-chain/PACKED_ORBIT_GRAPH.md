# One-word unit-folded orbit graph recipes

The graph builder in PR #293 uses an eight-byte C structure for each exact
predecessor recipe. The implicit variant in draft PR #295 removes those static
recipes but adds substantial integer work during preparation. This experiment
packs the same proven graph edge into one 32-bit word per orbit. The layout is
17 bits of parent orbit ID, 3 bits of unit code, 6 bits of compact digit ID,
4 bits of digit position, and 2 bits of nonzero digit depth. A 54-byte table
maps compact digit IDs to the existing 81-slot C digit table. The zero orbit
uses word zero. The generator must round-trip every recipe from PR #293
exactly before native evaluation.

The complete table has 9,843 width-10 orbits on the smaller schedule and
88,575 width-12 plus 1,095 width-8 orbits on the larger. Counting the shared
54-byte slot map, stored recipe data would shrink from 78,744 to 39,426
bytes and from 717,360 to 358,734 bytes. Point-table bytes and the online
scalar path are unchanged. Decoding a packed word adds one small slot-map
lookup per nonzero orbit during preparation; that lookup is explicitly
counted. This is an in-binary storage format, not a claim of lower total
process memory or faster CPU timing.

## Prospective gate

Commit this protocol, exhaustive packer, generated header, and proof report,
then open a draft PR before native evaluation. Compare the packed builder
with PR #293's stored-structure graph builder on the eight already frozen
public points in `orbit-graph-inputs.json`, alternating arm order. Require
all 32,768 candidate outputs to match independent generic digests, all
307,287 prepared entries to match on one generator per curve, all online
and curve-preparation operations to match the reference, exactly one slot-map
lookup per nonzero orbit, and exact static recipe-byte accounting. Preserve
raw failures. Measure timing only on a physical host that passes
`docs/ISOLATED_BENCHMARKS.md`; local timing is exploratory. Do not claim
academic novelty from bit packing. Public research scalars only.

## Frozen native panel

Draft PR #297 contained this protocol, header, and exhaustive round-trip
report before native evaluation. On generator, `37P`, `101P`, and `103P` for
both curves, all 32,768 packed-arm outputs matched independent generic
digests and all online and curve-preparation counters matched the stored
graph arm. The candidate performed exactly 39,368 and 267,910 compact
digit-slot lookups during preparation. Its recipe arrays plus shared slot
map occupy 39,426 and 358,734 bytes, compared with 78,744 and 717,360
bytes for the structure recipes. Preparation heap and point-table bytes are
unchanged. The native curve test matched all 307,287 prepared table entries
for generators on both curves and passed 1,030,887 checks.

The paired executable contains both recipe representations, so it does not
demonstrate lower total binary or resident memory. Raw runs, hashes, and
exploratory local times are in `packed-orbit-graph-panel.json`. No physical
host has passed the isolation gate, so CPU speed and one-target rho impact
remain unknown.
