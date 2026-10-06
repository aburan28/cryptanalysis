# Sparse hot-pair positional tau table

The [fused width-three τ scheme](TAU3_FUSED_POSITIONAL.md) prepares all 343
six-unit orbit representatives for each six-digit position. The [quotient
atlas](TAU3_QUOTIENT_ATLAS.md) makes its recoding cheaper, but its full point
table uses 43,904 and 76,832 bytes on the two study curves. This candidate
keeps the atlas recoder and uses a two-level point table.

For each block, prepare 18 one-digit half points: three seed orbits at each
of six τ positions. A two-digit orbit whose pair point is present in the hot
table uses one mixed addition, exactly as the full fused scheme. For a cold
pair, decode its two frozen representative patterns, apply the representative
and action units to the two half points, and use two mixed additions. Single
digits always use one half point. Thus every map action remains computable;
the hot selection affects operation count, not correctness. A scalar that
exceeds the prepared block capacity uses the explicit generic fallback.

The hot map is trained **only on older frozen action traces**. Orbit IDs
cannot be classified by numeric range: the 18 single-digit IDs are not
contiguous. The [generator](make_tau3_sparse.py) classifies each ID from the
frozen representative pair `(u,v)` and selects genuine two-digit orbits by
descending old-trace frequency, breaking ties by block then orbit ID. The
budget is twice the compact width-four table's point slots, including 18
half points per block and one spare block. This gives 396 and 756 prepared
points, or 12,672 and 24,192 point bytes. Cold pairs are supported in the
spare block. The generated maps and old-data counts are in the [screen
receipt](tau3-sparse-screen.json); the [read-only design
audit](audit_tau3_sparse_design.py) regenerates them from 32,768 old action
streams.

| Curve, four old point cases | Compact width-four additions | Full fused additions | Sparse prediction | Sparse point bytes |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 62,323 | 47,705 | 53,425 | 12,672 |
| j0-56 | 134,062 | 97,709 | 120,896 | 24,192 |

These figures are **retrospective predictions on the selection data**. They
are not a native result, CPU speedup, or academic novelty claim. A scratch
screen initially treated `id > 18` as a pair; that assumption was corrected
before generating this map or freezing any prospective inputs.

## Native and prospective gates

Freeze this generator, generated map, read-only design audit, and protocol
before native implementation. Native tests must verify every prepared half
and hot point, exhaustively exercise hot, cold, zero, and single actions,
and cover identity, subgroup-order, small-order, and over-capacity cases.
On older inputs, verify outputs against generic multiplication and preserve
raw action and group-operation counts as retrospective diagnostics.

After native source is frozen, generate a new 8 × 4,096-scalar fixture with
seed `0x5A31E0C4D9B8276F`, excluding all earlier scalar fixtures including
the quotient-atlas panel. Commit generic reference digests and a three-arm
paired runner before any `pos-compact`, `tau3-atlas-pos`, or
`tau3-sparse-pos` arm runs. The prospective operation gate requires all 24
arms to match the same generic outputs, zero candidate generic fallbacks,
exactly 396 / 756 sparse point entries, and strictly fewer sparse mixed
additions than compact width-four in all eight cases. Preserve every raw
failure and timeout. Controlled CPU timing requires a host-level isolation
receipt and repeated paired runs; local elapsed times are exploratory.
