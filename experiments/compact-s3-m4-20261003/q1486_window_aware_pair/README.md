# Q1486: exact cyclic-window pair domains

The [pre-registered design](design_protocol.json) tests an exact
window-aware replacement for Q1485's loose weight-bound leaf completion.
Q1485 rejected many unsupported partial states but did not find an
unpinned relation on either ordinary N53/N83 query. Its N83 ordinary
prefix made 8.57 million `S3` root calls and censored at 60 seconds.

Q1486 uses Q1482's exact six CNFs and public points without changing any
clause or target. The native variable map additionally exposes the
already-existing cyclic-window selectors and their ONB coordinate masks.
A leaf completion must be extendable to those selector assignments. This
lets the target-coupled pair domains enumerate the actual factor-base
shape while retaining the full Q1481 orbit-union base.

The first empirical gate is a fully unpinned known-satisfiable N83
decomposition, independently checked on the public point. The ordinary
N83 cell follows under the same frozen limits. A planted success alone is
not a natural-yield estimate. Q1486 remains a `Q` proposal with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`; its stage IDs
use Q1481's actual `B` values in the [frozen protocol](protocol.json):

- `PS1N53Ckb1fb430360PDP4hybridh5029e04bb3bb`
- `PS1N83Ckb1fb348006384PDP4hybridh55d5e1e8904f`

The [window-map receipts](inputs/) verify that all four selector rows and
the outside-window zero clauses already exist in each reused Q1482 CNF.
The [small-field control](window_validation.json) matched 59,049 partial
leaf/selector states to the original existential window clauses over
`F_32`, including overlapping and multiple selected windows. It checked
2,048 coupled guards against direct `S3` evaluation. The native source,
binary, input and map hashes, checked Sage runtime, limits, and stage IDs
were frozen before the six runs. No complete N131 `2^x` is implied.

The six frozen solver cells are pending. CPU wall times will be exploratory
without an isolated-host receipt.
