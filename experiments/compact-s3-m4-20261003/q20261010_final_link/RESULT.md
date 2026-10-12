# Q1432: exact target-coset S3 pruning in the compact four-summand search

Q1432 adds an in-search exact check of the final \(S_3\) link for the frozen
ordinary N53 and N83 four-summand workloads. Once both middle coordinates
are assigned, the callback rejects their pair unless an S3 root belongs to
the exact raw x-coordinate preimage set of the public target. It leaves the
original three-link CNF in place. In a 10-second, 5,000-conflict exploratory
grid, this checked 3,514 N53 and 1,501 N83 middle pairs under positive-first
branching; every checked ordinary pair was incompatible with its target
coset. All eight ordinary rows ended `BOUNDED_UNKNOWN`.

## Method and soundness

`build_targets.py` freezes the target x-coordinate sets from the Q1410 N53
and Q1408 N83 receipts. The ordinary files contain 428 and four distinct
coordinates respectively. Each is bound to the exact curve ID, workload ID,
actual usable factor-base size `B`, enumerated-set digest, and `isogeny:
"none"`. Control files use their own locked-target receipts. The C++ solver
accepts the target file as a new positional argument; `-` disables only this
new check for a same-binary comparison.

For fully assigned middle coordinates \(a,b\), `s3_roots` returns all
solutions \(t\) of \(S_3(a,b,t)=0\) when \(a,b\ne0\). The callback accepts the
pair exactly when one returned coordinate is in the frozen raw target set.
If either middle coordinate is zero, it evaluates \(S_3(a,b,t)\) directly for
each target coordinate. If none matches, it adds the clause that negates the
complete assignment of the two middle rows. Since those rows determine
\(a,b\), this clause excludes only an algebraically incompatible pair.
Memoization suppresses duplicate queries across backtracks. The check is
exact for the supplied target set and does not depend on a timing model.

`validate_final.py` exercises the callback on the locked N53 and N83
controls. Both accepted models pass an independent replay of all three S3
links, and each locked instance becomes UNSAT when the callback is given a
single deliberately incompatible target coordinate. An N11 fixed-coordinate
case separately tests both outcomes of the zero-middle branch. All checks
pass. The control models are correctness fixtures; the ordinary rows below
use the unpinned public targets.

## Ordinary search grid

The table uses the same Q1432 binary, frozen CNF/map, `satpivot` root
encoding, 5,000-conflict cap, and 10-second wall cap. `Final` selects the
exact target file; `Baseline` passes `-`. All runs have status
`BOUNDED_UNKNOWN`; `C` is reported CaDiCaL conflicts, `R` is first-link
exact root queries, and `F` is exact final-link rejections. Timings were
measured on an unisolated, contended host and are exploratory. The counts
describe search behavior, not completed-query cost.

| Field | Branch | Mode | CPU s | C | R | F | Status |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| N53 | allpos | Baseline | 7.38 | 5,001 | 4 | 0 | BOUNDED_UNKNOWN |
| N53 | allpos | Final | 8.50 | 0 | 3,410 | 3,514 | BOUNDED_UNKNOWN |
| N53 | allspread | Baseline | 3.63 | 5,000 | 4 | 0 | BOUNDED_UNKNOWN |
| N53 | allspread | Final | 8.48 | 63 | 1,777 | 3,406 | BOUNDED_UNKNOWN |
| N83 | allpos | Baseline | 8.90 | 1,891 | 206 | 0 | BOUNDED_UNKNOWN |
| N83 | allpos | Final | 8.77 | 0 | 1,488 | 1,501 | BOUNDED_UNKNOWN |
| N83 | allspread | Baseline | 8.79 | 1,976 | 80 | 0 | BOUNDED_UNKNOWN |
| N83 | allspread | Final | 9.05 | 62 | 751 | 1,414 | BOUNDED_UNKNOWN |

The target-coset clause changes which paths CaDiCaL explores. In
particular, the near-zero reported conflict counts for final-check rows
must not be read as completed solve progress: external-clause rejection and
CaDiCaL's internal conflict statistic have different boundaries. The raw
logs and `measurements.json` retain decisions, propagations, clauses,
literals, wall and CPU seconds, memory, cap flags, source and input hashes.
The ordinary N53 workload has a previously verified relation in its frozen
receipt, so the censored row is a search limitation, not an existence test.

## Work budget and next gate

The exact N131 W<=6 base has 25,036,774 folded columns. Q1414's
uniform-query supply bound requires at least 209,828,278 ordinary queries
for a 95% chance of full rank under its stated assumptions. Dividing an
abstract \(2^{61}\) total-work cap by that necessary query count leaves
less than \(2^{33.36}\) work units per query with every other cost set to
zero. This is a necessary affordability ceiling, not a measured solver
cost. Q1432 has no completed ordinary point decomposition at N53 or N83,
so measured work per successful query, an N131 solve exponent, and the
gap to \(2^{61}\) remain null in `measurements.json`.

The next search change should apply the same exact target-coset reasoning
as soon as the **first** middle coordinate is fixed. By S3 symmetry, each
raw target coordinate yields at most two compatible values for the second
middle coordinate. This leaves at most eight choices at N83 and 856 at
N53, before the second leaf pair is explored. A guarded membership
constraint can test whether this earlier propagation recovers the known
N53 ordinary relation and then an ordinary N83 relation. Measure natural
yield and novel rank on fresh ordinary queries before fitting any N131
\(2^x\) projection.

## Reproduction

From the repository root, use Q1430 `prepare.py` to regenerate each
`/private/tmp/q1430_*` CNF/map. Its metadata checks the frozen XCNF SHA and
the archived formula. Then run:

```sh
python3 experiments/compact-s3-m4-20261003/q20261010_final_link/build_targets.py --degree 53
python3 experiments/compact-s3-m4-20261003/q20261010_final_link/build_targets.py --degree 53 --mode control
python3 experiments/compact-s3-m4-20261003/q20261010_final_link/build_targets.py --degree 83
python3 experiments/compact-s3-m4-20261003/q20261010_final_link/build_targets.py --degree 83 --mode control
sh experiments/compact-s3-m4-20261003/q20261010_final_link/build.sh /private/tmp/q1432_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_final_link/validate_final.py --binary /private/tmp/q1432_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_final_link/run_grid.py --binary /private/tmp/q1432_insearch --wall 10 --conflicts 5000
```

`run_grid.py` refuses a mismatched curve, workload, base digest, target
file, or CNF before measuring. The solver's interface is `CNF MAP
TARGETS_OR_MINUS S3_MODULE_DIR FIELD_DIR BRANCH_POLICY ROOT_ENCODING
WEIGHT_BOUND CONFLICT_CAP WALL_SECONDS`. The executable and all measured
inputs are identified by SHA-256 in `measurements.json`.
