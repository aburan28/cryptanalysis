# Sound partial-output gate for adjacent W14 pair sums

An adjacent Frobenius-window W14 pair can be rejected from a **partial raw
output coordinate** before its missing low bits or source masks are chosen.
On the exact ECC2K-130 field, 60 invariant equation rows from the top 115
bits rejected **512/512** frozen uniform field controls while retaining all
**16/16** independently replayed source-pair outputs. With the top 111 bits
known, the gate rejected **498/512** controls. These are sound whole-prefix
rejections: an inconsistent projected equation excludes every completion of
the unspecified low bits. A consistent prefix still requires exact pair
inversion and group replay.

This is a component of the proposed adjacent-window geometry, with
`candidate_id: null` and `target_count: 0`. The field is
`GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is `y²+xy=x³+1`, with
subgroup order `680564733841876926932320129493409985129`. The existing
[adjacent pair oracle](../n131_w14_adjacent_pair_inverse_20261010/RESULT.md)
uses rotations `[0,1,26,27,52,53,78,79,104,105]`, 8,220 audited source
masks, 163,800 distinct usable projected factor-base points, and 8,160
signed-Frobenius columns. Its independent checked-Sage audit replayed the
16 positive raw group sums used here.

## Projected equation

For a pair, let `s=w_a+w_b²` and `p=w_a w_b²`. Their respective spaces have
dimensions 21 and 40. If `z=1/(x(P_a+P_b)+1)` is defined, the exact equation
is

```text
z² = HT(s)² + (z²+z)p.
```

Write `z=z_hi+δ`, where only bits `0..b−1` of `δ` may be nonzero.
Squaring and `A(z)=z²+z` are binary-linear, so changing the low bits
changes the equation by exactly `δ²+A(δ)p`. The [producer](run.py) builds
the coordinate mask `I_b` of rows where `δ²` and `A(δ)p_j` vanish for
every low-bit basis vector and every one of the 40 product-space basis
vectors. Projecting onto `I_b` leaves a 61-column binary-linear system
in the 21 seed and 40 product coefficients. If its right side is outside
the column span, **no low-bit completion and no source pair** can have
that prefix. The [independent audit](audit_result.json) recomputed every
span decision with a separate elimination loop, checked the invariant
derivatives, and checked the exact positive identity against the archived
source masks.

## Frozen controls and result

The [first protocol](protocol.json) bound the existing 16 positive outputs,
16 field controls, source hashes, one worker, 120-second stage cap, and
4-GiB RSS cap before the [first run](result.json). The
[second protocol](controls_protocol.json) fixed a PRNG seed and 512
uniform 131-bit field coordinates before the [larger panel](controls_result.json).
All 16 positives were consistent at every tested first-panel width. The
second panel reports sound span rejection for its declared uniform input
law; the 95% Wilson intervals quantify only that law, not ordinary target
relation yield.

| Unknown low bits `b` | Invariant rows | Uniform controls rejected | 95% Wilson interval for rejection |
| ---: | ---: | ---: | ---: |
| 0 | 131 | 512/512 | 0.9926–1.0000 |
| 12 | 68 | 512/512 | 0.9926–1.0000 |
| **16** | **60** | **512/512** | **0.9926–1.0000** |
| 18 | 56 | 510/512 | 0.9859–0.9989 |
| 20 | 52 | 498/512 | 0.9546–0.9836 |
| 22 | 48 | 318/512 | 0.5783–0.6621 |
| 24 | 44 | 32/512 | 0.0446–0.0869 |

At `b=16`, all 512 projected systems had rank 47 of 61. The first
positive/control panel also measured widths 4, 8, 28, and 32; all records,
including consistent controls, are retained. The 32-input first stage
completed in 0.617 seconds with 24,526,848-byte peak RSS. The 512-input,
seven-width panel completed in 14.368 seconds with 25,100,288-byte peak
RSS. These are complete local stage intervals on an unisolated host;
there is no controlled CPU speedup claim. The audit checked **3,872**
saved span rows and the 16 earlier Sage group replays.

## Algorithm choice and next gate

The adjacent schedule nearly doubles the distinct projected base points
of the existing repeated-rotation W14 schedule, while this projected
linear gate leaves only 16 low output bits unspecified at its observed
512/512 control-rejection point. The [repeated-rotation prefix
inverse](../n131_w14_high_prefix_inverse_20261010/RESULT.md) completed
its smaller control panel with 35 low bits unspecified. These are different
frozen input panels, so their rates are stage diagnostics; actual relation
yield, novel rank, and target-dependent cost must decide the geometry.

The next useful test is an **unpinned public-target N41 upper-chain query**
that records when it can expose a pair-output prefix, how many adjacent and
repeated-rotation prefix gates it calls, and how many whole families each
soundly rejects before exact mask inversion. An N131 promotion then needs a
source-bound complete-query estimate within one worker, 600 seconds, and
4 GiB, followed by ordinary relation replay. This panel by itself does
not generate target-conditioned pair-output prefixes.
