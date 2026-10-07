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

The operation panel is prospective relative to the frozen table selection,
but the current implementation is a Python correctness and operation model.
It has no native online timing, preparation timing, isolation receipt, or
speedup claim. The point table uses 32 bytes per entry in the current C
representation, so the total prepared point payload is 79,808 and 153,664
bytes respectively, before metadata and temporary storage. The extra table
requires an additional point preparation step for each extra entry. Scalars
and table lookups are public; the proposed lookup is variable-time.

## Reproduce the frozen artifacts

From this directory, run the commands below. Existing outputs must match
byte-for-byte; generators reject changed frozen outputs.

```sh
python3 make_tau3_scatter_design.py . tau3-scatter-design.json
python3 make_tau3_scatter_inputs.py . tau3-scatter-design.json tau3-scatter-inputs
python3 check_tau3_scatter_panel.py . tau3-scatter-design.json \
  tau3-scatter-inputs/inputs.json tau3-scatter-panel.json
```

The native candidate still needs table preparation, matching, complete
output verification on the frozen panel, and an isolated host receipt before
any wall-time comparison is promotable. The format is an experimental design;
its relationship to prior scattered precomputation literature has not yet
been established as an academic novelty claim.
