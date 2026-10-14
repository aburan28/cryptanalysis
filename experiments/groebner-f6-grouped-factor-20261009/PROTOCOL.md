# Bit-sliced grouped S3 factor experiment

The static S3 chain has nine Boolean coordinate equations for each field
equation over GF(2^9). The predecessor builds one dense truth table per
coordinate. This candidate packs all nine coordinate coefficients into a
16-bit word, performs one Boolean Möbius transform over their union scope,
and admits an assignment exactly when all nine output bits are zero. The
existing exact static elimination, cached witnesses, fresh target factors,
and original-equation checks remain the query path.

For Boolean polynomials `f_0,...,f_(k-1)` with `k <= 16`, let their packed ANF
coefficient at monomial `S` be `C_S = sum_i c_(i,S) 2^i` with XOR addition.
The Boolean zeta transform is linear over each output bit, so its packed
result at assignment `a` has bit `i` equal to `f_i(a)`. Consequently, the
combined factor predicate `C(a)=0` is **exactly** the conjunction of the
original coordinate equations. Duplicate input monomials cancel modulo two
before forming the union scope. This proof applies to any explicitly grouped
Boolean equations, not only S3. It does not lower the union support width;
grouping can be counterproductive when equations have very different scopes.

The frozen field is the checked GF(2^9) representation, curve parameter
`b=1`, fixture seed 1, and all 512 target abscissae in ascending order. The
summand abscissa law is `0 <= x < 2^ell`. Independent curve-sum enumeration
lifts every allowed abscissa with both signs, takes all `m`-fold group sums,
and determines the finite target abscissae. The native solver must agree on
every target; each satisfiable witness must pass the original ANF equations
and curve-point replay. The matched predecessor message solver runs on the
first three cases; it is expected to hit its unchanged 200-million-state
construction cap on the two six-bit cases.

| Field bits | Summands | Coordinate bits | Seed | Maximum bag | Predecessor |
| ---: | ---: | ---: | ---: | ---: | --- |
| 9 | 4 | 4 | 1 | 22 | Complete comparator |
| 9 | 4 | 5 | 1 | 23 | Complete comparator |
| 9 | 5 | 5 | 1 | 23 | Complete comparator |
| 9 | 4 | 6 | 1 | 24 | Expected state cap |
| 9 | 5 | 6 | 1 | 24 | Expected state cap |

Both optimized and UBSan builds run every case. Each completed grouped query
uses fresh target coefficients and a fresh native solve; only static factors
and witness history are reused. The complete target-dependent interval begins
before target equation generation and ends after independent ANF and point
replay. Setup, fixture construction, independent curve enumeration, and
artifact serialization are separate. Pair arm order alternates on target
parity. The driver retains each arm in a flushed JSONL journal and updates a
compressed report after each case. A failed arm, missing row, status mismatch,
or failed witness check fails the panel.

Before the curve panel, deterministic random ANF systems over six Boolean
variables exercise group sizes 1, 3, 9, and 16, including duplicate monomial
cancellation and constant terms. Their native statuses and witnesses are
compared with independent exhaustive enumeration of all 64 assignments.
The four-summand, seven-bit case is an expected width-cap control because its
middle-link union scope has 25 variables, above the unchanged max-bag 24.

The acceptance gate is 5 x 2 x 512 = 5,120 grouped target runs, plus
3 x 2 x 512 = 3,072 matched predecessor runs, exact curve and ANF replay,
all random-system controls, and the two state-cap and one width-cap controls.
The build script checks committed candidate and predecessor source bytes and
stores optimized/UBSan binary hashes. The validation driver checks every
executed Python source against the frozen commit. CPU timing remains a
diagnostic until an isolated host receipt passes the repository contract;
`timing_eligible=false` and `qualified_speedup=null` stay in the report.

From a clean full checkout, build the source-bound predecessor chain as in
`.github/workflows/groebner-f6-grouped-factor.yml`, then run:

```sh
python3 experiments/groebner-f6-grouped-factor-20261009/build.py
python3 experiments/groebner-f6-grouped-factor-20261009/validate.py \
  --output /absolute/path/to/new-evidence-directory
```
