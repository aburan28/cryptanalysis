# Fixed-seed reciprocal pair circuit on the degree-131 challenge curve

The fixed-seed pair identity gives an exact 17-bit source encoding for each of
eight two-point groups. It produces a complete 16-summand, target-conditioned
native-XOR formula with 602,369 live Boolean IR operations. A constructed
16-point relation solves and independently checks against every one of its
1,399,623 XCNF constraints. On one frozen ordinary public point, CryptoMiniSat
entered search and reached the 615-second parent cap; a matrix-enabled probe
on the identical formula reached its separate 195-second parent cap.

## Geometry and equation

The field is `GF(2^131)` in the polynomial basis with modulus
`t^131+t^13+t^2+t+1`; the curve is `y^2+xy=x^3+1`. Its prime subgroup order is
`r=680564733841876926932320129493409985129`. The canonical curve ID used by
this experiment is `EC1N131Ckb1heb5f1998f20b`. The prior public-target file
uses an older ID alias for the same exact field, curve, and subgroup.

For a point with `x != 1`, put `u=1/(x+1)`. The reciprocal third summation
polynomial can be written

```text
G(u,v,z) = (uvz+u+v+z)^2
         + uvz(uv+uz+vz+u+v+z+1) = 0.
```

For source coordinates `w_a=u_a^2+u_a` and `w_b=u_b^2+u_b`, the pair output
coordinate `z` obeys the equivalent equation

```text
z^2 + (u_a+u_b)^2 = (z^2+z) w_a w_b.
```

Fix `w_b=w_a+s` with source-mask seed `s=212`. Then
`u_a+u_b=half_trace(s)` is constant, while
`w_a w_b=w_a^2+s w_a` is linear in the 17 free source-mask bits after fixing
the pivot bit of `s` to zero. The Sage symbolic equality and 32 exact group
checks are in [derive_result.json](derive_result.json). An exact reduced BDD
restricts each 17-bit selector to rational source masks whose two projected
points have distinct folded columns; [pair_preflight_result.json](pair_preflight_result.json)
checks all `2^17` selector assignments. Seven `G` links join the eight
Frobenius-rotated pair outputs. Nonzero pair and intermediate coordinates
exclude denominator degeneracies. Any solver model must still pass the exact
curve and cross-slot column replay in [replay_ordinary_model.py](replay_ordinary_model.py).

The source is the audited W18 mask-to-column table. Scanning seeds 1 through
255 selected seed 212 with 33,191 valid unordered source pairs per slot,
66,318 distinct folded columns, and 66,382 rational masks per window. Eight
rotations `0,16,32,48,64,80,96,112` give 1,062,112 usable projected points
before orbit folding, using the earlier audited nonoverlap geometry. The exact
BDD has 13,093 nodes. The labeled tuple count divided by `r` is 141.831661;
this is a support ceiling before cross-slot column exclusions and does not
measure ordinary decomposition yield. [support_result.json](support_result.json)
preserves the full seed scan and source hashes.

## Frozen target and measured stages

The public one-target workload ID is `cc09e7eb202a`, with
`Q=(1052727368764798954359115163823647684025,
2071227447786120917960296877345506689833)`. The checked Sage launcher
computed all four raw preimages under `[4]` and verified each; the formula
fixes the reciprocal coordinate of preimage index 0. The recorded
target-dependent preimage computation took 5.9335 ms, excluding Sage startup.
The solver uses one worker, a 4 GiB parent-enforced RSS cap, and the exact
source/formula/binary hashes in the protocol and result JSON files.

| Stage | Result | Boundary |
| --- | --- | --- |
| Exact source membership | 33,191 codes per pair; 13,093 BDD nodes | W18 mask table, seed 212, eight rotations |
| Full circuit | 1,965 field-bit roots; 602,369 live IR operations | Eight pair equations and seven reciprocal `G` links |
| Constructed formula | 890,036 variables; 765,358 CNF clauses; 634,265 XOR rows | All source selectors, pair outputs, and intermediate outputs pinned |
| Constructed solver and audit | SAT in 2.020 s, peak 220.7 MB; all 765,358 clauses and 634,265 XOR rows passed an independent model audit | Wiring and completeness control |
| Ordinary formula | 889,295 variables; 763,388 CNF clauses; 633,524 XOR rows | One frozen public target preimage, selectors and intermediates free |
| Ordinary solver | `PARENT_TIMEOUT` at 615.051 s; peak 532.8 MB; about 267,000 logged conflicts | CryptoMiniSat5, one thread, 600 s solver cap plus 615 s parent cap |
| XOR-matrix probe | Four matrices activated; `PARENT_TIMEOUT` at 195.062 s, peak 502.1 MB; Gaussian elimination later auto-disabled at 10.23% usefulness | Same formula; 180 s solver cap plus 195 s parent cap; matrix limits 10,000 rows and 15,000 columns |

The [full_preflight_result.json](full_preflight_result.json) evaluates all roots
on the constructed curve row and on the ordinary target with the constructed
leaves held fixed. The constructed model's independent streamed audit is
[full_planted_model_audit.json](full_planted_model_audit.json). The ordinary
formula and solver have SHA-256 receipts in [full_ordinary_build.json](full_ordinary_build.json)
and [full_ordinary_solver_result.json](full_ordinary_solver_result.json); the
matrix probe is in [matrix_probe_result.json](matrix_probe_result.json).
Both ordinary runs started actual search. Their capped status is
`BOUNDED_UNKNOWN`, with parent stop reason `PARENT_TIMEOUT`; neither is a proof
of unsatisfiability. The matrix probe changed the solver configuration and
limit, so its conflict count is diagnostic rather than a paired speed ratio.

This is a point-decomposition stage experiment. The candidate ID remains
`null` while relation collection, rank novelty, factor-log LA, target recovery,
and matched one-target rho remain to be specified and measured. The next
experiment should change the target-search representation while holding the
exact source and public point fixed: the pair equation has only 17 selector
bits but the chained reciprocal circuit leaves six 131-bit intermediate
coordinates. A useful next gate is a smaller-field and N131 matched study of
eliminating or preconditioning those intermediates, with exact curve replay
and ordinary-query completion probability measured at frozen caps.
