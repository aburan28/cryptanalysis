# Q1495: fixed-window tuple support screen

Q1495 derives a conditional support and work screen for solving four-point
decompositions one **fixed ordered tuple of cyclic windows** at a time on
Q1484's exact N131 base. Its [design](design_protocol.json) and [R2
recovery protocol](recovery_protocol.json) bind the audited base census,
curve, subgroup order, counted factor-base points, source, and checked Sage
runtime. This is proposal `Q1495`, with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`.

The first N53 direct control failed while serializing a projected point's
redundant normal-basis integer into seven bytes. The [R1 failure
record](runs/r1/failure.json) preserves the exception; it produced no
validated count. The separately frozen R2 uses canonical `onb.toCoords()`
masks before serialization. It directly tested all 16,383 nonzero raw `x`
values in one N53 length-14 window, found **8,257** rational values, and
verified **16,514** distinct, nonidentity subgroup points after the exact
cofactor-428 projection. The [R2 control](n53_direct_window_control_r2.json)
was independently recomputed and matches the span-incidence calculation
from Q1481's exact census.

## Exact one-window count

For `2d<n`, each eligible nonzero raw `x` orbit has a unique long zero gap
and a unique minimal containing arc. An orbit with span `s` has exactly
`d-s+1` Frobenius rotations inside any specified length-`d` window. If
`R_s` is the audited number of rational raw `x` orbits of span `s`, the
number of rational `x` values in one window is

`R_window = sum_s R_s (d-s+1)`.

The Q1484 census has zero identity projections and zero duplicate
projected orbits. Its odd-order subgroup therefore supplies two distinct
usable points per rational `x`. The exact N131 result is
`R_window = 67,101,345` and **`B_window = 134,202,690`** subgroup-usable
points before sign/Frobenius folding. This per-window count is separate
from the full union-base `B = 8,790,494,834` and folded
`K = 33,551,507`, both on `EC1N131Ckb1h6816f880945e` with set digest
`d3fa5abbd34df91d48731d283b4960f6110d8202c452a8bd349baa907bb4a331`.

## Conditional support and work bound

One fixed ordered four-window tuple contains at most `B_window^4`
ordered subgroup-point quadruples. Each quadruple sums to one target.
For a uniform nonidentity subgroup target, the chance that any such
quadruple sums to it is at most

`B_window^4/(r-1) = 4.7662349128e-7 < 2^-21.0006`.

The union bound then gives a necessary number of **target-independent
oriented window tuples** before the schedule's support upper bound can
reach a chosen level. It does not assert that the schedule achieves that
support.

| Desired support level | Necessary fixed tuples |
| ---: | ---: |
| 1% | 20,981 (`2^14.357`) |
| 10% | 209,810 (`2^17.679`) |
| 25% | 524,524 (`2^19.001`) |

If each tuple inspection returns **at most one** verified relation and all
`K` folded columns must be supplied by these uniform-target queries, rank
cannot exceed the number of returned relations. Markov's inequality makes
**66,874,445,412,288** (`2^45.927`) tuple inspections necessary for at
least 95% probability of full rank, even if every returned row is novel.
For total work strictly below `2^61`, their average charged cost must be
below **34,480.2** (`2^15.073`) operations per tuple in the *same named
accounting unit*, with all other costs set to zero. This is an optimistic
affordability ceiling, not a measured per-tuple solver cost or an N131
complete-solve exponent.

The [R2 screen](screen_result_r2.json) stores the exact integer and rational
inputs, decimal support bound, source hashes, and claim scope. The bound
applies to a tuple schedule fixed independently of each uniform target.
It does not constrain a target-adaptive tuple schedule, a solver that
reasons jointly across many windows, or a solver that returns multiple
verified relations from one tuple. A solver may share work between tuples;
the result does not charge a separate formula build to every inspection.
Natural relation yield, final matrix solving, target descent, scalar
replay, and the complete N131 `2^x` remain unknown. The challenge gate
stays closed.

## Reproduce

```sh
python3 experiments/compact-s3-m4-20261003/q1495_window_tuple_screen/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/q1495_window_tuple_screen/freeze_recovery.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1495_window_tuple_screen/validate_n53_r2.py --check
python3 experiments/compact-s3-m4-20261003/q1495_window_tuple_screen/screen_r2.py --check
```
