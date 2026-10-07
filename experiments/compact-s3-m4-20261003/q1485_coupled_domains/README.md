# Q1485: target-coupled exact pair-domain intersection

The [pre-registered design](design_protocol.json) tests one solver change on
Q1482's exact N53/N83 window-orbit bases and byte-identical six-cell inputs.
Q1482's native theory commits to a second midpoint and then spends many
direct `S3` evaluations on right-pair completions that have no support.
Q1485 builds exact left and right midpoint domains while both leaf pairs are
still partial, intersects them under the public target, and emits guarded
clauses for empty intersections or forced midpoint bits.

Each domain enumerates at most 4,096 weight-`d` pair completions. That set is
a superset of every window-valid completion in the unchanged Q1482 CNF, so
an empty intersection is a sound rejection. The bounded domain is a local
stage mechanism; success on a planted point does not measure ordinary yield.
Both ordinary public targets remain exactly those used by Q1482.

Q1485 remains a `Q` proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. Stage IDs will use Q1481's actual `B` counts after source,
binary, and input hashes are frozen. The complete N131 `2^x` remains unknown.
