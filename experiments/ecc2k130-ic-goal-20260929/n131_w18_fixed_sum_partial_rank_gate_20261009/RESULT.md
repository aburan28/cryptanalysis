# A fixed-sum rank gate rejects partial N131 pair outputs earlier

**Conditioning the W18 pair product on its seed sum and choosing the free
output bits by structural rank gives a sound earlier rejection gate.** On the
frozen 32-sum panel, all 96 exact raw pair outputs passed every gate. With
40 output bits still free, only **9 of 2,048** matched sum/control decisions
passed the rank-minimizing gate, versus **477 of 2,048** when the free bits
were the contiguous low 40. With 48 bits free, the same comparison was
**590 versus 2,048**. An independent low-pivot implementation reproduced
every selected bit and decision; checked Sage replayed representative raw
pairs for all 32 sums.

## Exact necessary condition

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)`, and the unrotated W18 seed
space is `V=span(t,...,t^18)`. For a fixed nonzero seed sum `s=w_1+w_2`,
the pair product lies in `P_s=image(L_s|_V)`, where
`L_s(w)=w²+sw`. Its kernel is `{0,s}`, so `dim(P_s)=17`.
For the raw pair-output coordinate `z=1/(x(P_1+P_2)+1)`, the exact cleared
pair equation is

`z² = H(s)² + epsilon + (z²+z)p`, with `p∈P_s`.

Suppose a search has assigned the bits outside a chosen set `U` and writes
`z=z_0+sum_{i∈U} d_i t^i`. Choose a basis `b_j` of `P_s`. Expanding the
equation and replacing each bilinear product `d_i p_j` by an independent
binary variable gives a necessary **linear** consistency test. Its columns
are

`1`, `t^{2i}` for `i∈U`, `(z_0²+z_0)b_j`, and
`(t^{2i}+t^i)b_j` for `i∈U`.

The right side is `z_0²+H(s)²`. Every genuine pair supplies a solution to
the relaxed system; an inconsistent system safely rejects that partial
output and seed sum. Consistency remains a necessary condition, followed
by the exact pair inverse and group checks.

The [producer](run.py) chooses `U` one bit at a time to minimize the rank of
the output-independent columns `1,t^{2i},(t^{2i}+t^i)b_j`, breaking ties
by the lowest bit index. This choice uses only `s` and the field; it sees
neither a candidate output nor the control decisions. Its comparison policy
leaves the contiguous low `k` bits free. Both policies use exactly 40 or
48 free bits for each sum.

## Frozen 32-sum panel

The [protocol](protocol.json) binds the source, checked
[Sage runtime](sage_runtime_info.json), prior independently audited W18
oracle, and its 64 balanced-trace field controls. The oracle contributes
32 nonzero seed sums and three distinct nonexceptional raw outputs per sum.
Every one of those 96 outputs passes all four policy/bit-count decisions.
The controls are reused against each sum, so the 2,048 cells are a fixed
matched panel, rather than independent samples of relation yield.
Proposal `Q20261009192000` has `candidate_id: null` and `target_count: 0`:
this is a pair-gate stage for a future target-linked solver.

| Free output bits | Contiguous low: controls passing | Rank-minimizing: controls passing | Rank-minimizing per-sum pass range | Base-rank range, low / chosen |
| ---: | ---: | ---: | ---: | ---: |
| 40 | 477 / 2,048 | **9 / 2,048** | 0–2 of 64 | 109–113 / 105–108 |
| 48 | 2,048 / 2,048 | **590 / 2,048** | 8–40 of 64 | 125–129 / 112–114 |

The [result](result.json) retains every selected bit position, the full
greedy rank trace, all 384 positive and 8,192 control decisions, and the
four policy totals. The independent [audit](audit.json) implemented field
multiplication by carryless shift/reduce and used **low-pivot** binary
elimination, whereas the producer used the imported field engine and
high pivots. It reproduced every chosen bit, rank, and decision. Checked
Sage additionally verified 64 field products, all 18 half-traces, and 32
representative raw curve additions and phi outputs.

| Frozen structural stage | Wall nanoseconds |
| --- | ---: |
| Build rank-17 images and field-bit blocks | 1,361,779,332 |
| Choose free bits for 32 sums | 9,123,989,835 |
| Evaluate four policies on 96 positives and 2,048 controls | 5,916,341,707 |
| Interval overhead | 1,984,251 |
| **Charged structural total** | **16,404,095,125** |

Field and input setup took another 79,303,500 ns outside that structural
interval. Peak producer RSS was 22,200,320 bytes. The separate independent
audit used 16,645,316,250 ns. These local CPU times describe this fixed
panel; they have no host-isolation receipt. The 300-second and 4-GiB caps
and exclusive phase sum are checked in the audit.

## Next target-linked gate

The result supplies a compact exact **necessary** check once the public
target's S3 constraints have fixed a seed sum and the complementary 83 or
91 output bits. The next experiment must make those assignments arise
before choosing both pair leaves. On the frozen N41 public point, it should
count partial families rejected while multiple pair domains remain free,
then recover and independently replay an unpinned relation within the
120-second/4-GiB control. A whole-search N131 work and memory projection
must include target-side production of `(s,z_0)` states and failed gate
calls before promotion to the 600-second ordinary relation query.
