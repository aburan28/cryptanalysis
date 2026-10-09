# Compact exact pair inverse for an N131 d13 same-rotation policy

The exact degree-131 d13 factor base supports a six-pair, twelve-summand
policy with rotations `[0,0,22,22,44,44,66,66,88,88,110,110]`. Each
adjacent pair uses the same 13-dimensional source subspace before its
common Frobenius rotation. This change preserves the audited full
factor-base policy of **B=1,083,108 subgroup points and K=4,134 folded
columns**, while giving each pair a compact seed-sum inverse. It is proposal
`Q20261009212400`; its candidate and run IDs remain null until the
complete algorithm is specified and queried.

Let `A(t)=t²+t`, let `a,b` be the two leaf phi values in the same subspace
`V`, and fix their sum `s=a+b≠0`. If `z` is the phi coordinate of their
point sum, the exact S3 equation becomes

`A(z) [A(a)² + A(s)A(a)] = (s+z)²`.

The bracketed map `L_s(a)` is binary linear in the 13 unknown seed bits.
Its kernel is exactly `{0,s}`: in the field, `L_s(a)=A(a)[A(a)+A(s)]=0`,
so `a` lies in `{0,1,s,s+1}`; the frozen d13 subspace does not contain the
field element `1`. Thus **every nonzero seed sum has rank 12**. For a
proposed `z` with `A(z)≠0`, divide the right side by `A(z)`, solve the
cached 131-by-13 binary map, test both recovered seed codes for usable
curve lifts, and verify the two signed curve additions. One index at
rotation zero applies to all six pairs by Frobenius conjugation.

The [frozen protocol](protocol.json) binds the exact N131 geometry, full
candidate manifest, checked-Sage runtime, source hashes, all 8,191 nonzero
seed sums, and positive/control inputs. The producer enumerated all 4,134
usable d13 selectors and partitioned the **8,542,911 unordered distinct
code pairs** by seed sum. Every sum bucket is nonempty, with 973–1,102
unordered pairs. The [cached pivot index](pivots.bin) is **1,974,044 bytes**
for all sums; it stores an inverse map rather than the pair-output set.

| Measured local stage | One frozen execution |
| --- | ---: |
| Selector and pair-count geometry | 6.145 s |
| All 8,191 cached rank-12 maps and index serialization | 1.076 s |
| Positive and negative controls, including two complete-sum scans | 0.370 s |
| Full-sum inverse of one positive output | 0.157 s |
| Full-sum inverse of one sampled control output | 0.140 s |
| Peak process RSS | 45,318,144 B |
| Frozen total wall / RSS caps | 600 s / 4 GiB |

The [run receipt](result.json) records all 32 positive pair outputs and
128 sampled fixed-sum controls. Every positive output recovered its two
codes and passed exact point addition; none of the sampled controls
passed. The complete scan over all 8,191 sums returned the saved positive
pair and no pair for its sampled control output. These controls check the
inverse, not natural target yield. The [independent audit](audit.json)
re-enumerated the valid selectors, reconstructed all 98,292 stored pivot
rows from field products, checked 16 Sage GF(2) matrices, and replayed all
positive group outputs and both full scans. A separate
[rotation audit](rotation_audit.json) passed 48 signed-output checks across
the six scheduled rotations. The host has no isolation receipt, so all
times above are exploratory local-stage costs.

The index avoids enumerating up to 17,085,822 pair-output x descriptors,
but a six-pair search still needs the public target to generate compatible
`(s,z)` values. The exact descriptor count gives at most 34,171,644 signed
two-leaf group outputs, a uniform-subgroup support ceiling of
`5.022×10⁻³²`; blind residual lookup is therefore not the next search
rule. The constructive gate is a target-coupled six-pair solver using this
inverse as an exact theory check, first on a frozen ordinary N41
same-rotation control and then, with source-bound work and memory limits,
on the N131 public point. An independently verified N131 relation, useful
rank, factor logs, fresh-target scalar, and matched one-target rho timing
remain the full-pipeline gates.
