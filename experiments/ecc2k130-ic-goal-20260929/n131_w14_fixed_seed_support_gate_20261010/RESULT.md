# Exact coupled W14 support count selects the twelve-leaf gate

The W14 source contains **11,604,167,458** four-mask, four-column quartets
whose XOR is zero. Allowing both signs for each atom gives at most
**185,666,679,328** projected four-atom group outputs when the common seed
may vary. For a ten-leaf relation with this one same-rotation block and six
other W14 leaves, a uniformly sampled subgroup point lies in the resulting
support with probability at most **0.005386112**. Fixing the seed to mask 1
lowers that ceiling to **0.000000986269**. These are rigorous source-support
ceilings, independent of the cost of a membership oracle. A twelve-leaf
version is not excluded by the same cardinality test and is the next arity
to test with target-conditioned propagation.

This counts a proposed repeated-slot W14 family on
`EC1N131Ckb1heb5f1998f20b`: four leaves use one rotation of the audited
W14 source, and each remaining leaf has at most 16,440 signed choices from
one W14 rotation. The existing ten-source geometry has **B=164,400** usable
points across ten rotations and **K=8,160** folded columns. Repeated slot
positions, relation length, and collection policy still require a complete
candidate manifest, so `candidate_id` is `null`. A distinct-column rule
can only reduce the support ceilings below.

## Exact counting argument

Let `M` be the 8,220 audited rational W14 masks and `κ(a)` their folded
column IDs. For each nonzero source-mask sum `s`, form the unordered
mask-pair set

`P_s={(a,b): a<b, a⊕b=s, κ(a)≠κ(b)}`.

The [first count](result_bounds.json) found 33,780,028 such mask pairs over
all 16,383 nonzero seeds, with 2,062 at seed 1. A valid pair of members of
`P_s` has four distinct folded columns. If `c_s=|P_s|`, `d_{s,j}` counts
pair incidences at folded column `j`, and `m_{s,jk}` counts pairs using
the same two columns, its exact number is

`C_s = binom(c_s,2) − Σ_j binom(d_{s,j},2) + Σ_{j<k} binom(m_{s,jk},2)`.

The last term corrects double subtraction when two pairs share both
columns. Every valid XOR-zero quartet appears in exactly **three** seed
pairings, one for each perfect matching of its four masks. Hence
`Q=(Σ_s C_s)/3=11,604,167,458`. At seed 1,
`C_1=2,124,877`. Each quartet has at most 16 sign assignments, giving
the four-atom group-support ceilings `16Q=185,666,679,328` over variable
seeds and `16C_1=33,998,032` for seed 1. Group collisions or source
constraints can only lower those numbers.

For relation length `m`, the remaining `m−4` leaves contribute at most
`16,440^(m−4)` sums. With subgroup order
`r=680564733841876926932320129493409985129`, the uniform-point union
bound is `min(1, S_4·16,440^(m−4)/r)`. The ratios before clipping are:

| Relation length | Fixed seed 1 | Any common seed |
| --- | ---: | ---: |
| 10 leaves | 9.862686×10⁻⁷ | 0.005386112 |
| 12 leaves | 266.562371 | 1,455,723.976 |

The bound uses a uniformly sampled point from all `r` subgroup elements.
For a uniformly sampled nonidentity point, replace `r` by `r−1`; the
displayed precision is unchanged. The frozen public point is one fixed
input, so these probabilities prioritize candidate design rather than
decide membership for that particular point. Ratios above one mean this
counting test gives no useful probability ceiling at that arity.

## Complete N41 group replay

On `EC1N41Ckb1h7d5e80d3c4d0`, the audited W6 source has 32 rational
masks. The complete [checked-Sage group census](support_n41_v2.json)
found **540** distinct XOR-zero, four-column mask quartets and **8,640**
distinct signed group outputs across all 63 seeds. Seed 1 has **28**
compatible quartets and **448** distinct group outputs. Thus every
quartet/sign assignment gives a distinct group point on this N41 source;
the count's `16Q` upper bound is exact there. The constructed positive
four-atom output from the earlier [inverse control](../n131_w14_coupled_fouratom_inverse_20261010/inputs.json)
is in the seed-1 set. The frozen N41 public point is outside both the
seed-1 and all-seed four-atom sets.

The [independent audit](audit.json) brute-counted all N41 four-mask
quartets and independently enumerated compatible pair pairs for N131
seeds 1, 8191, and 16383. It matched the complete
[N131 count](quartet_result.json), including divisibility by three and
the N41 group-support count.

The first N41 producer completed its arithmetic, but its parent monitor
could not enumerate macOS processes; [that failure](failure_v1.json)
preserves unknown parent wall and RSS for the first run. The frozen
[version-two replay](protocol_v2.json) used direct process RSS monitoring
after the checked repository Sage launcher. It produced byte-identical
mathematical counts in **4.579 s parent wall** and sampled peak Sage
process RSS **262,078,464 bytes**, below the 120-second and 4-GiB caps.
The [parent receipt](sage_run_v2/receipt.json) and
[checked Sage runtime](sage_runtime_info_v2.json) preserve those boundaries.
The monitor samples the Sage process after the launcher exec; startup
runtime verification is included in parent wall, while the process RSS
figure is for that direct process. These CPU timings are exploratory on an
unisolated host.

## Next target-conditioned experiment

Freeze a twelve-leaf policy with one same-rotation four-atom block and eight
other W14 positions. Derive candidate partial outputs from the public
point jointly with at least two still-free blocks, then apply the exact
four-atom inverse before source enumeration. On the unpinned N41 public
control, measure family rejection before leaves are chosen, verified
ordinary relations, rank novelty, complete wall/RSS, and exact replay.
Promote to the frozen N131 point only with a source-bound whole-search
projection under one worker, 600 seconds, and 4 GiB. The cardinality result
above rules out blind residual probing as a useful way to exercise the
four-atom inverse at ten leaves.
