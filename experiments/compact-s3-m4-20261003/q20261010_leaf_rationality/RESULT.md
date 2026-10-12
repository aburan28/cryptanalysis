# Q1434: exact curve-rationality clauses for four-summand leaves

Q1434 rejects leaf x-coordinates that cannot belong to the Koblitz
\(b=1\) curve before querying an S3 pair root. The solver checks the exact
Artin–Schreier trace condition at each fully assigned leaf and inserts a
clause for a nonrational x. For leaves at the normal-basis weight bound,
the clause needs only the positive bits: the existing at-most-weight
constraint determines every remaining bit. This reduces the mean
nonrational-leaf guard from 53 to 4.45 literals at N53 and from 83 to 6.68
at N83 in the short exploratory grid. Both locked N53/N83 controls remain
satisfiable and independently replayed; all ordinary search rows remain
`BOUNDED_UNKNOWN`.

## Mathematical and implementation rule

The exact curves are `EC1N53Ckb1hf77aab617904` and
`EC1N83Ckb1h876c2921cb64`, with `isogeny: "none"`. For their model
\(y^2+xy=x^3+1\), a nonzero x is a rational curve x-coordinate exactly
when

\[
\operatorname{Tr}_{\mathbb F_{2^n}/\mathbb F_2}
  \left(x+x^{-2}\right)=0.
\]

Indeed, substituting \(z=y/x\) gives \(z^2+z=x+x^{-2}\), whose field
solution criterion is zero trace. The x=0 case has the rational solution
y=1. Every factor-base leaf must satisfy this condition. It is a necessary
curve-membership filter; subgroup and exact base-column checks remain
separate components of a completed relation verification.

The callback runs before Q1431 pair-root propagation and Q1433 early-target
propagation. `full` excludes a nonrational leaf with all n assigned bit
literals. `sat` uses only its positive literals when the leaf has exactly
the formula's weight bound w; under the frozen at-most-w clauses, those w
positive bits identify that x uniquely. For an undersaturated leaf, `sat`
uses the full n-bit guard. `off` retains the Q1433 behavior in the same
binary. Each rejected x is memoized with its leaf row, and all supplied
clauses are valid throughout backtracking.

## Frozen ordinary screen

The short grid uses the exact Q1410 N53 and Q1408 N83 ordinary target
points and bases, `satpivot`, Q1433 `selector`, a 5,000-conflict cap, and a
10-second wall cap. The N53 base has actual usable B=24,062 and folded
K=227; the N83 base has B=30,977,592 and K=186,612. All rows ended
`BOUNDED_UNKNOWN`. `C` is leaf checks, `X` is nonrational leaves excluded,
`L` is submitted leaf-guard literals, and `R` is first-link S3 root queries.

| Field | Branch | Leaf mode | C | X | L | Mean L/X | R |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| N53 | allpos | off | 0 | 0 | 0 | — | 291 |
| N53 | allpos | full | 3,270 | 1,696 | 89,888 | 53.00 | 1,572 |
| N53 | allpos | sat | 3,129 | 1,625 | 7,225 | 4.45 | 1,502 |
| N83 | allpos | off | 0 | 0 | 0 | — | 870 |
| N83 | allpos | full | 1,127 | 560 | 46,480 | 83.00 | 565 |
| N83 | allpos | sat | 851 | 417 | 2,787 | 6.68 | 432 |
| N83 | allspread | sat | 1,079 | 509 | 3,091 | 6.07 | 568 |

The state counts differ across modes because each clause changes the
search path. The exact mean guard lengths demonstrate encoding
compression; they are not a wall-time speedup. CPU time on this host was
only about 1–2 seconds during each 10-second wall interval because the
host was heavily contended. Every row retains its raw CPU/wall, conflict,
decision, propagation, memory, clause, and cap counters in
`measurements.json`.

The two extended `allpos`/`sat` runs used 100,000-conflict and 120-second
wall caps:

| Field | Status | CPU s | Pair-root queries | Leaf checks | Nonrational leaves | First-middle values checked | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | BOUNDED_UNKNOWN, wall cap | 17.25 | 15,820 | 24,865 | 12,830 | 1 | 311,689,216 bytes |
| N83 | BOUNDED_UNKNOWN, wall cap | 27.89 | 7,328 | 14,694 | 7,364 | 1 | 501,727,232 bytes |

The first-middle state remained fixed in both extended runs. Their search
work therefore measures a narrow branch region and does not estimate
ordinary-query completion cost. The original S3 CNF, exact target-coset
constraints, and relation checks remain available for any future model.

## Independent validation and work accounting

`validate_leaf.py` replays all 56 archived rejected-leaf samples with a
separate field-trace computation. Every sample has trace one and obeys the
frozen weight bound. Five degree-11 fixed-coordinate cases exercise x=0,
rational and nonrational x, a full nonrational guard, a weight-saturated
short guard, and the undersaturated fallback under explicit at-most-two
clauses. Both locked controls produce S3 models with four rational leaves
and pass independent replay. `validation.json` records `PASS`.

The exact N131 W<=6 uniform-query supply bound leaves less than
\(2^{33.36}\) work units per ordinary query under an abstract \(2^{61}\)
total cap with every other cost set to zero. No Q1434 ordinary run completed
a point decomposition, so successful-query work, natural relation yield,
novel-row rate, a fully charged N131 \(2^x\) projection, and the challenge
gap remain null in the measurement record.

## Next experiment

Move the `sat` rationality test to the moment a leaf reaches w positive
bits, before its remaining negative assignments have been propagated.
Screen decision orders that vary the first leaf pair and first-middle
state, including `allspread` and offset/stride policies, on the frozen
N53 known-satisfiable ordinary target and N83 ordinary target. The next
acceptance gate is a verified ordinary N53 four-point decomposition,
followed by an ordinary N83 decomposition and natural useful-row/rank
measurements. Charge all failed attempts and arithmetic before fitting a
degree-131 solve exponent.

## Reproduction

Rebuild Q1430's frozen CNF/map and Q1432's exact target files as documented
in their respective directories, then from the repository root run:

```sh
sh experiments/compact-s3-m4-20261003/q20261010_leaf_rationality/build.sh /private/tmp/q1434_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_leaf_rationality/run_grid.py --binary /private/tmp/q1434_insearch --wall 10 --conflicts 5000
sh experiments/compact-s3-m4-20261003/q20261010_leaf_rationality/run_long.sh /private/tmp/q1434_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_leaf_rationality/record_long.py --binary /private/tmp/q1434_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_leaf_rationality/validate_leaf.py --binary /private/tmp/q1434_insearch
```

`run_grid.py` and `record_long.py` verify curve, workload, actual B, base
digest, target SHA, CNF SHA, measured source, and executable SHA. The
solver CLI extends Q1433 with `LEAF_MODE` between `EARLY_LIMIT` and
`WEIGHT_BOUND`.
