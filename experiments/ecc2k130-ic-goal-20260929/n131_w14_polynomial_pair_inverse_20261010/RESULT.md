# Exact W14 polynomial pair-output inverse on ECC2K-130

The W14 polynomial source admits a **41-column exact joint inverse** for
same-rotation leaf pairs on the degree-131 challenge curve. Its product
span has dimension 27, so a proposed pair output first faces a
131-by-41 binary consistency gate. On the frozen panel, the gate recovered
all 32 independently constructed pair outputs and rejected all 32 uniform
field controls before the fixed-sum inverse. An independent checked-Sage
audit reproduced every rank decision and positive group sum. This turns a
proposed pair output into an exact mask-pair query; generating outputs
compatible with the upper decomposition links remains the next task.

For `A(v)=v²+v`, a same-rotation pair with source masks `a,b`, transformed
sum `z`, and `s=a+b` satisfies

`z² = u_s² + A(z) w_a w_b`.

The `u_s²` terms lie in a 14-dimensional binary space. With
`w_i=t^i`, `i=1..14`, every `w_a w_b` lies in the span of
`t²,...,t²⁸`, dimension 27. At full joint rank 41, one linear solve
determines the unique candidate sum mask `s`; an exact fixed-sum linear
solve of `w_a²+w_s w_a=P` then enumerates its kernel, filters the audited
rational masks and distinct folded columns, and returns every accepted
unordered pair. A joint rank drop falls back to all 16,383 nonzero seed
sums. For `z=0`, the equation forces equal masks, excluded by distinct
columns. For `z=1`, it forces `u_s=1`; the audited W14 `u` space has
rank 15 after adjoining 1, so that branch is empty.

The [frozen protocol](protocol.json) uses the exact polynomial field
`t^131+t^13+t²+t+1`, curve `y²+xy=x³+1`, and official prime subgroup of
order `680564733841876926932320129493409985129`. The [source support](../n131_w14_ten_source_gate_20261009/RESULT.md)
has 8,220 rational masks and 8,160 sign/Frobenius-folded columns. This
proposal pairs equal rotations at `[0,0,26,26,52,52,78,78,104,104]`;
the five distinct rotated source spaces have **82,200 actual usable
projected factor-base points** before folding. It changes the factor-base
policy from the ten-distinct-rotation formula. The exact source-space
intersection and subgroup evidence comes from the previously audited W14
support; the complete IC candidate ID remains null.

| Exact degree-131 evidence | Result |
| --- | ---: |
| Same-rotation W14 product-span rank | **27** |
| Rotation difference 13 product-span rank | **131** |
| Joint columns / full ranks on nonexceptional controls | 41 / 64 of 64 |
| Constructed positive outputs recovered | **32 of 32** |
| Uniform field controls rejected by span gate | **32 of 32** |
| Exceptional coordinates checked | `z=0`, `z=1` |
| Exhaustive 16,383-sum comparators with identical pair sets | One positive, one uniform |
| Peak process RSS / complete panel wall | 21,299,200 bytes / 17.503 s |

The [input record](inputs.json) fixes the 32 positive raw group outputs,
32 uniform field controls, two exceptional coordinates, their seed, and
the selected exhaustive comparisons. The [run receipt](result.json)
preserves every query result and phase cost. Median joint query walls were
0.377 ms for positives and 0.211 ms for uniform controls; the two
exhaustive comparisons took 7.690 and 6.439 seconds. These CPU timings
are exploratory on an unisolated host. The exact operation boundary is
more useful here: the positive full-rank branch tests one seed sum and
the span-reject branch tests none, while exhaustive inversion tests all
16,383. The [independent Sage audit](sage_audit.json) recomputes the
rank-27/rank-131 product spans, the 41-column rank and consistency for
all 64 nonexceptional inputs, the recovered seed sums, every positive
group sum, and subgroup membership; its [runtime receipt](sage_runtime_info.json)
identifies the checked Sage build. The [terminal audit](terminal_audit.json)
binds these artifacts to source and input hashes.

The rank-131 mixed-rotation result explains why the joint span gate does
not transfer to the previous `[r,r+13]` leaf pairing: its relaxed product
space fills the field. The next gate is a same-rotation ten-source
decomposition on a fixed target. It must generate compatible pair outputs
for the upper four S3 links, invoke this exact inverse on proposed outputs,
and measure verified ordinary relations and novel rank within the frozen
resource envelope. Constructed positives are correctness controls, not
ordinary relation-yield measurements.
