# Forward roots for the four-block target join

The functional two-root circuit reproduces the independently verified
12-point N41 relation from its source masks and eight quadratic branch
bits. Pinning those eight bits makes the complete target-ended formula
solve in **1.100 s** with one worker. With only the source masks fixed,
the same formula reached its **65.201 s** wall cap after active search.
This identifies branch selection under the target equation as the next
solver bottleneck. The proposal is `Q20261009220100`; its
`candidate_id` is `null` because this diagnostic does not specify a
complete IC pipeline.

## Exact method and input

The field is `GF(2^41)` with modulus `t^41+t^3+1`. The Koblitz curve is
`y^2+xy=x^3+1`, with prime-order subgroup
`r=549756390943` and the frozen public point
`Q=(1458168294740,1672312028033)` in polynomial-basis integer
encoding. The four factor-base rotations are `0,10,20,30`; the actual
four-rotation base has `B=504` usable subgroup points and `K=57`
folded columns. The [source experiment](../n41_n131_zero_sum_triple_20261009/RESULT.md)
returned a verified relation on this point.

For each W7 block, choose ordered masks `a<b<c` with `c=a XOR b` and
require all three source points. The half-trace coordinates satisfy
`u1+u2+u3=0`. The exact product `w1*w2` is a 13-coordinate convolution
of the two low-degree source masks. For every two-point link, the output
coordinate `z=1/(x(P1+P2)+1)` satisfies

```text
P(z^2+z) = (u1+u2+z)^2,  P=(u1^2+u1)(u2^2+u2).
```

The circuit computes its two roots using the odd-degree half trace and
one branch bit. Each triple has two links, so four blocks expose eight
branch bits. The second link combines the first pair sum with the third
leaf. The four block outputs enter the exact target-ended S5 invariant
with one of the four raw preimages of `Q` under multiplication by four.
The independent Sage chart records the nonexceptional link products,
root bits, and raw point sums in [forward_chart.json](forward_chart.json).

The [frozen protocol](protocol.json) hashes all formulas, builders,
inputs, the accepted checked-Sage runtime, and the CryptoMiniSat binary.
Its primary control pins only the eight source mask vectors. The chart
also pins the pair and block outputs, eight root bits, and target fiber;
the branch probe pins only the root bits in addition to the source masks.
The public formula pins none of these values.

| Formula or run | Variables | CNF clauses | Native XOR rows | AND gates | Solver result | Solver wall | Peak sampled RSS |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Public formula, built only | 248,003 | 410,183 | 111,710 | 136,225 | Gate closed | — | — |
| Fixed-mask control | 248,003 | 410,239 | 111,710 | 136,225 | `BOUNDED_UNKNOWN` | 65.201 s | 321,617,920 B |
| Fixed-mask and root-bit probe | 248,003 | 410,247 | 111,710 | 136,225 | `SAT_MODEL` | 1.100 s | 122,224,640 B |
| Fully pinned chart | 248,003 | 410,579 | 111,710 | 136,225 | `RECOVERED_CHART_MODEL` | unknown | unknown |

The fixed-mask run used `--threads=1 --maxtime=60`, a 4-GiB combined
RSS cap, and an outer 65-second wall cap. Its [raw log](control/stdout.txt)
shows roughly 300,000 conflicts before the wall cap; it did not report
SAT or UNSAT. [Its result](control/result.json) and the checked-Sage
[audit](control/audit.json) retain the censored status. The root-bit probe
used the same worker and memory envelope with a 30-second solver limit;
its [model](branch_probe/result.json) passes all 410,247 clauses and
111,710 native XOR rows and matches the chart outputs and target fiber.
These wall timings are exploratory because this host has no isolation
receipt.

The first chart run found a complete SAT model and checked its formula
assignment, then the receipt writer failed on `KeyError: mask_wire_rows`:
the chart-build metadata contains pins but the mask wire rows live in the
control-build metadata. The original [stdout](chart/stdout.txt) and
[model bits](chart/model_bits.txt) remain intact. A separate
[recovery check](chart/recovered_result.json) verified all 410,579 chart
clauses and 111,710 XOR rows against those bytes; its wall interval is
unknown. [Independent checked-Sage replay](chart/recovered_audit.json)
reconstructed all 12 raw and projected leaves, their root branches,
distinct folded columns, and the exact sum to `Q`. The [receipt verifier](verify.py)
checks frozen hashes, all measured statuses, the complete models, and
the replay record.

## Next experiment

The eight witness branch bits are privileged control data, so their
1.100-second solve measures propagation after branch selection. A
target-conditioned solver must select them from the public point and
source masks. The next N41 test will put the eight branch variables and
source-mask variables ahead of circuit auxiliaries in a frozen search
order, then measure an unpinned public solve and the number of mask
families rejected before expanding all branch combinations. Any returned
row must be replayed from raw points. N131 promotion remains gated by an
unpinned N41 result and a source-bound one-worker, 600-second, 4-GiB
projection; no N131 query was launched in this iteration.
