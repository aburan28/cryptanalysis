# Packed coefficient rows for Boolean F4

This opt-in candidate packs each column-indexed matrix row into 64-bit coefficient
words over GF(2). Monomials still use the existing Boolean mask representation
(up to 64 variables) and descending grevlex column order. The baseline is the
round 61 bounded scratch-vector reducer; both arms use round 60 leased ANF inputs.

The first set bit selects the same pivot as the sparse row's first column. Each
XOR updates packed words and recomputes the number of nonzero terms with popcounts.
That count preserves the original leading-term and XOR work charges. Every XOR
emits the same witness with the same parents, including XORs producing zero rows.
Output rows are expanded and sorted into the unchanged public representation.
All ordinary and Boolean completion checks and the independently rebuilt checker
remain in the query path. Numeric rows and pivots are fresh for every matrix;
no target coefficients, answers, elimination state or proof IDs are reused.

The packed coefficient payload is bounded by 8,388,608 words (64 MiB), excluding
vector metadata and other solver storage. Before allocating it, the selector
uses division to check `row_count * words_per_row` without overflow. Matrices
above that bound use the sparse scratch reducer. The older 262,144-column guard
also remains. This is a memory guard, not a demonstrated performance crossover;
the candidate is not enabled as a default. The tiny four-word test arm exercises
both sides of the payload boundary.

The frozen complete-query interval includes descent/input filling, conversion
into packed matrix rows, pivot search, XOR and popcounts, proof generation,
output expansion, independent certification, extraction, original-equation and
curve replay, and lease teardown. Invariant layout preparation and fixture
construction remain separate. Historical work-counter equality does not measure
the added conversion cost or the changed physical arithmetic cost; full wall time
is the acceptance metric.

Validation runs 15 test groups, then 728 direct matrix cases on each of three
variants in optimized and UBSan builds. These 4,368 records cover column counts
0, 1, 3, 4, 5, 63, 64, 65, 127, 128, 129, 255, 256 and 257, both low and bit-63
monomial masks, ordinary and near-UINT64_MAX work budgets, and proof-node limits.
Python independently replays XOR proofs and compares reduced row spaces, and all
variants must have identical numeric outputs and proof/work prefixes. The full
92-record query panel additionally matches frozen bases, proofs and counters and
replays solved curve controls. Artifact auditing never executes foreign binaries.

```sh
python3 experiments/groebner-perf-20260924/round62/run_validation.py --output packed-evidence
```

CI rebuilds on Linux x86-64 and macOS ARM64. Other platforms are untested. See
`RESULTS.md` for this candidate and `CI_BASELINE.md` for the qualified measurement
of the earlier F4 changes. These are solver-stage experiments, not complete IC
candidates, a rho comparison, a new F5 implementation or an asymptotic F6 claim.
