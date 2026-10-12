# Q1433: target-coset propagation after the first S3 middle coordinate

Q1433 constrains the second middle x-coordinate as soon as the first is
assigned. It uses exact S3 roots against the frozen public target's raw
x-coordinate preimages, then inserts guarded support clauses during CaDiCaL
search. On the N83 ordinary input, one first-middle value had eight
compatible second-middle values; the selector encoding reached 4,024
first-link root queries in a 10-second capped run. On the N53 ordinary input,
the first 20 checked middle values had no compatible target-coset root.
Independent discriminant replay confirms all sampled rootless states.
Every ordinary grid row remains `BOUNDED_UNKNOWN`.

## Exact construction

Given the first middle coordinate \(a\) and a raw target x-coordinate \(t\),
the callback computes all \(b\) such that \(S_3(a,t,b)=0\). Symmetry of S3
makes these exactly the permissible second-middle coordinates for the final
link. It takes the union over the complete frozen target set. There are at
most two roots per nonzero target coordinate, hence at most eight choices
for N83's four target coordinates and 856 for N53's 428 coordinates. Zero
inputs use the exact identity \(S_3(0,u,b)=(ub)^2+1\); two zero inputs have
no root. The original three-link CNF and Q1432 final-link callback remain
active.

`selector` adds one observed Boolean variable per distinct allowed root.
Under the complete assignment guard for \(a\), at least one selector must
hold; each selector implies every bit of its root. `consensus` adds only
middle bits shared by all allowed roots. A rootless set adds the guard as a
conflict clause. `off` preserves Q1432 behavior in the same binary. The
explicit early-query limit bounds clause growth, especially at N53; skipped
states receive no early constraint but retain the original CNF and final
check. All clauses are valid for the frozen target coset.

## Ordinary hyperparameter screen

The grid uses the exact Q1410 N53 and Q1408 N83 ordinary CNF and target
sets, `satpivot`, 5,000-conflict and 10-second wall caps. `E` counts unique
first-middle states checked early; `Z` counts states with no compatible
second-middle root; `R` counts Q1431 pair-root queries; `F` counts Q1432
final-link rejections. The host was unisolated, so CPU timings describe only
these runs. All rows ended `BOUNDED_UNKNOWN`.

| Field | Branch | Early mode and limit | CPU s | E | Z | Max allowed roots | R | F |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | allpos | off | 8.10 | 0 | 0 | 0 | 3,058 | 3,178 |
| N53 | allpos | selector 5 | 3.46 | 5 | 5 | 0 | 631 | 1,325 |
| N53 | allpos | selector 20 | 6.45 | 20 | 20 | 0 | 2,485 | 2,580 |
| N83 | allpos | off | 7.76 | 0 | 0 | 0 | 1,275 | 1,282 |
| N83 | allpos | consensus 100 | 7.67 | 1 | 0 | 8 | 1,644 | 883 |
| N83 | allpos | selector 100 | 7.64 | 1 | 0 | 8 | 4,024 | 0 |
| N83 | allspread | selector 100 | 7.29 | 100 | 100 | 0 | 578 | 889 |

The N83 selector run explores more pair-root states under the same wall cap,
but it has not completed an ordinary decomposition. Its final-link
rejection count is zero because the early support constraint changes the
search path. Comparing raw conflicts or root queries across these bounded
runs is a search diagnostic, not a solve-time ratio.

`validate_early.py` independently recomputes the S3 quadratic trace for
21 archived rootless middle coordinates against **every** target x in their
respective frozen sets. All 21 are rootless, and all 21 nonzero middle x
values have curve-rationality trace one for the Koblitz \(b=1\) equation.
This identifies a concrete source of wasted search: the compact weight
constraint admits x-coordinates that do not represent rational curve
points. Six degree-11 fixed-coordinate cases exercise zero inputs,
equal inputs, zero roots, and two roots; positive and incompatible choices
match direct S3 evaluation. Both locked N53/N83 controls still produce
independently replayed S3 models. The validation status is `PASS`.

## Work estimate and next gate

The exact N131 W<=6 base's uniform-query supply bound leaves less than
\(2^{33.36}\) work units per ordinary query under an abstract \(2^{61}\)
total cap with all other costs set to zero. Q1433 has no completed ordinary
PDP call at either measured degree. The measured successful-query work,
N131 full \(2^x\) solve projection, and challenge gap therefore remain
null in `measurements.json`.

The next improvement is to test curve-rationality clauses at the **leaf**
coordinates, before the first S3 pair root is queried. This should remove
the traced invalid x states earlier and leave the exact factor-base
weight and subgroup filters visible in the candidate manifest. First ask
whether it recovers the archived N53 ordinary four-point relation, then
measure an ordinary N83 query on the exact Q1325 base. Preserve failed
attempts, relation yield, novel rank, and complete operation accounting
before projecting to N131.

## Reproduction

The Q1430 CNF/map files and Q1432 target files are the inputs. From the
repository root:

```sh
sh experiments/compact-s3-m4-20261003/q20261010_early_target/build.sh /private/tmp/q1433_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_early_target/run_grid.py --binary /private/tmp/q1433_insearch --wall 10 --conflicts 5000
python3 experiments/compact-s3-m4-20261003/q20261010_early_target/validate_early.py --binary /private/tmp/q1433_insearch
```

`run_grid.py` checks the exact curve, workload, actual base size and digest,
target-set SHA, and CNF SHA before executing. The solver interface adds
`EARLY_MODE EARLY_LIMIT` between Q1432's `ROOT_ENCODING` and
`WEIGHT_BOUND`. `measurements.json` binds source, executable, input, log,
resource cap, and status for every row.
