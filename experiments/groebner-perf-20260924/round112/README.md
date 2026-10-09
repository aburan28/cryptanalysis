# Early parity compression preserves useful matrix candidates

The matrix producer now tries parity proof compression before ordinary graph
pruning. A successful rewrite avoids both ordinary reachability/remapping passes.
This lets three additional frozen 12-variable point-decomposition queries retain
their matrix candidates within the existing work cap and complete with native
seeded F4. Every accepted final basis is independently checked against the
original equations and replayed on the curve.

The opt-in `early_query.Query` uses the same leased packed-input API, reusable
layouts, four-column elimination tables, native continuation and owned binary
certificate transport as round111. `early_mode=0` selects the previous order;
`early_mode=1` attempts compression first. Coefficients, elimination and checking
are performed afresh for each query. All failed work remains charged to the
shared producer/checker budgets.

## Why the compressed graph is strictly smaller

Let `R` be the set of proof nodes reachable from the output references. Ordinary
pruning retains exactly `|R|` nodes. For each node, reverse XOR propagation
computes a bitmask indicating the outputs in which that node occurs with odd
parity. Let `A` be the nodes whose mask is nonzero when they are visited.

Every node in `A` has a path to at least one output, so `A` is a subset of `R`.
Direct input ancestors of monomial-multiple leaves need not be counted in `A`;
omitting them only strengthens its role as a lower bound. Therefore

`|A| <= |R|`.

The rewrite constructs each output by XORing its surviving input/monomial leaves.
Linearity over GF(2) preserves the represented polynomial. It is accepted only
when the emitted graph has `C < |A|` nodes. Consequently

`C < |A| <= |R|`,

which proves strict improvement over ordinary pruning without constructing the
reachability array. Testing against the raw graph size alone would be incorrect:
unused nodes could make an equal-size retained proof appear smaller. The unit
controls include exactly that counterexample.

The transform handles XOR nodes and direct monomial multiples of original input
nodes. It retains the existing 64-output and metadata-byte limits. Unsupported
shapes, missing roots, an unsuccessful size bound or a metadata limit preserve
the original graph and take the ordinary pruning fallback. Work exhaustion
returns an inconclusive producer result. Partial attempts remain charged; the
node cap is never reset or enlarged.

## Reproduction

From the repository root, with Python 3.13 and a C++17 compiler:

```sh
python3 experiments/groebner-perf-20260924/round112/run_validation.py --output /absolute/new/validation
python3 experiments/groebner-perf-20260924/round112/profile.py --reference-report /absolute/new/validation/panel/report.json --output /absolute/new/profile
```

Validation makes fresh optimized and UBSan builds, runs exact native/Python
matrix-model comparisons and all small resource-budget prefixes, then executes
the unchanged thirteen-case panel in both compression modes and both build
modes. The independent audit replays matrix operations and work charges, checks
the strict size inequality, verifies final proof derivations and Boolean bases,
and replays curve solutions. Thirteen deliberately corrupted artifacts exercise
the acceptance boundary. `--reuse-reference` records reuse of existing
source-matched round108/110 libraries while rebuilding the early-parity producer.
All recorded source files must be committed before execution.

Profiling uses the same complete-query boundary and output format in both arms:
fresh coefficient descent, matrix production, bounded fallback or seeded F4,
independent certificate verification, owned proof copying, bounded solution
extraction, current and independently generated equation/curve replay, and lease
teardown. Target-independent fixture/layout preparation and artifact serialization
stay outside this interval. One warmup and four observations use AB/BA/BA/AB order.
Failed and capped runs remain in the record. Controlled CPU speedup promotion
requires the repository's host-isolation receipt.
