# Scattered width-three τ pair table

This is an experimental public-scalar multiplication format for the two
prime-field `j=0` subgroup instances in this directory. It adds selected
nonadjacent pairs to the complete six-step τ orbit table. The online recoder
computes a maximum-cardinality matching among the nonzero three-step blocks:
each selected pair consumes one mixed group addition, and each unmatched block
consumes one. A pair within the same six-step block is always available from
the existing complete table. A pair across six-step blocks is available only
when its position and common-unit orbit are in the frozen extra table.

The point identity is exact. A three-step block at position `i` contributes
`τ^(3i) D_u`. For a prepared extra entry `(i,j,u,v)`, the point is
`τ^(3i) D_u + τ^(3j) D_v`. The six common units
`{±1, ±ω, ±ω²}` fold equivalent entries. At runtime the selected unit acts
on the prepared point. Because matched pairs are disjoint, summing the
selected points and unmatched singles reconstructs the original τ expansion.
Maximum matching minimizes the number of mixed additions for the **fixed**
expansion and prepared table. It does not minimize preparation, recoding,
lookup, field, or wall-clock cost.

Formally, let `t` be the number of nonzero three-step blocks and let an edge
join two blocks exactly when their pair is prepared. A set of pair actions
is a matching because a block cannot be used twice. If the matching has
`m` edges, it covers `2m` blocks and leaves `t−2m` singles, for `t−m`
online additions. Therefore maximizing `m` gives the minimum addition count
within this action alphabet. The proof assumes the selected scalar expansion
is fixed; choosing among different expansions is a separate optimization.

## Frozen selection and fresh operation panel

[`make_tau3_scatter_design.py`](make_tau3_scatter_design.py) ranks cross-pair
orbits using the earlier `compact-pos` scalar fixture. It first removes
singles that the complete six-step table already pairs, then counts pairs of
the remaining singles. The table budgets were fixed at one extra full-table
allocation per curve. The small curve had only 1,122 distinct eligible
entries, so 250 of its 1,372 extra slots remain unused. This design was
frozen before [`make_tau3_scatter_inputs.py`](make_tau3_scatter_inputs.py)
generated a new 32,768-scalar panel disjoint from four earlier fixtures.

[`check_tau3_scatter_panel.py`](check_tau3_scatter_panel.py) runs exact
matching on that panel, verifies the Eisenstein coefficient identity and
scalar congruence for all 32,768 scalars, and independently replays 184
elliptic-curve point outputs. All eight cases passed.

| Subgroup instance | Full six-step additions | Scatter additions | Saved additions | Extra point entries | Total point entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 47,756 | 44,160 | 3,596 (7.53%) | 1,122 | 2,494 (1.82× full) |
| `j0-56` | 97,726 | 93,177 | 4,549 (4.65%) | 2,401 | 4,802 (2.00× full) |

The native implementation in `src/ec_tau.c` prepares the extra points by
adding two affine points from the existing six-step table, then normalizes
them in one batch inversion. It uses a binary search over the frozen extra
table and an exact dynamic-programming matching over at most 20 nonzero
three-step blocks. Larger recodes use the generic multiplier and are counted
as fallbacks. This is a public-scalar, variable-time method.

[`check_tau3_scatter_native_panel.py`](check_tau3_scatter_native_panel.py)
replays the fresh fixture through both C modes in alternating order. All 16
arms verified their full generic point outputs; candidate and control point
digests matched in all eight cases; candidate additions and matched-pair
counts exactly matched the frozen Python model; fallbacks were zero.
Preparation used 2,418 versus 1,296 group additions on `glv-j0-32`, and
4,669 versus 2,268 on `j0-56`, with the latter counts for the complete
six-step table. The point table uses 32 bytes per entry, giving 79,808 and
153,664 prepared point bytes respectively, before metadata and temporary
storage. The largest online dynamic-programming memo allocated on the panel
was 64 bytes for the small curve and 4,096 bytes for the large curve.
The release and UndefinedBehaviorSanitizer `test_curve` suites each passed
2,308,720 checks after adding scalar edges, forced over-capacity fallback,
and identity-point controls. The UndefinedBehaviorSanitizer native panel
passed all 16 arms as well. A combined AddressSanitizer and
UndefinedBehaviorSanitizer build passed with warnings as errors, but its
macOS AddressSanitizer process stalled in runtime allocator initialization
before `main`; that runtime test is unverified. The Linux CI sanitizer job
is the remaining cross-platform sanitizer gate.

The native receipt records local online and preparation timings only as
exploratory data. It has no isolation receipt or wall-time speedup claim.
The extra preparation cost and online matching/search cost must be included
in any future isolated comparison.

## Reproduce the frozen artifacts

From this directory, run the commands below. Existing outputs must match
byte-for-byte; generators reject changed frozen outputs.

```sh
python3 make_tau3_scatter_design.py . tau3-scatter-design.json
python3 make_tau3_scatter_inputs.py . tau3-scatter-design.json tau3-scatter-inputs
python3 make_tau3_scatter_map.py tau3-scatter-design.json ../../src/generated/tau3_scatter.h
python3 check_tau3_scatter_panel.py . tau3-scatter-design.json \
  tau3-scatter-inputs/inputs.json tau3-scatter-panel.json

# From the repository root, after building with CA_BUILD_TAU_CHAIN_BENCH=ON:
python3 experiments/prime-j0-cost-aware-chain/check_tau3_scatter_native_panel.py \
  /absolute/path/to/ca_tau_chain_bench \
  experiments/prime-j0-cost-aware-chain/tau3-scatter-native-panel.json
```

An isolated host receipt is still required before any wall-time comparison
is promotable. The format is an experimental design; its relationship to
prior scattered precomputation literature has not yet been established as
an academic novelty claim.

The digit set and unit actions are built on established work for prime-field
`j=0` curves, including [Heuberger and Mazzoli's symmetric digit sets](https://eprint.iacr.org/2013/705.pdf).
[Faster implementation of scalar multiplication](https://eprint.iacr.org/2012/519.pdf)
also describes τ-NAF precomputation and its storage/preparation tradeoff for
binary curves. Neither source is evidence that this particular matching
format is new; a broader prior-art review is still needed before publication.
