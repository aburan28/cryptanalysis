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
`isogeny: "none"`. The [frozen stage protocol](protocol.json) uses Q1481's
actual usable `B` counts and Q1482's byte-identical six-cell inputs:

- `PS1N53Ckb1fb430360PDP4hybridhffb34db82440`
- `PS1N83Ckb1fb348006384PDP4hybridhb9502b103ea2`

The [small-field control](coupled_validation.json) exhausted 5,103 left
target/pair-state domains, 729 right pair-state domains, and 157,464 domain
filters under partial midpoint masks over `F_8`. It also checked 16,384
seeded coupled four-leaf guards against direct `S3` evaluation. This checks
the mathematical pruning rule at that size; the pinned public-point cells
check the native implementation at N53/N83. The complete N131 `2^x` remains
unknown.

The six frozen solver runs are pending. All CPU wall times will be labeled
exploratory without an isolated-host receipt.
