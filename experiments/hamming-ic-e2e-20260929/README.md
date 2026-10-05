# FC-Hamming in a complete toy index-calculus DLP

The later, separate [N53 weight-three root-index study](N53_W3_ROOT.md)
completed three independently replayed one-target DLPs. It uses a
four-summand root index rather than this FC-Hamming SAT method. Its Mac CPU
timings lack an isolation receipt and are exploratory; controlled speedup is
unknown.

This experiment puts the factorized-convolution (FC) Hamming predicate from
La Scala, Marchesin, and Tiwari's [*Hamming Ideals and Gröbner Bases for
ISD-like Syndrome Decoding*](https://arxiv.org/abs/2609.18866) into a complete
five-summand elliptic-curve index-calculus pipeline. It compares the FC
predicate with the earlier unary exact-weight counter, holding the curve,
factor base, S3 chain, solver limits, relation policy, matrix solve, target,
and one-worker resource envelope fixed. The only algorithmic difference is
the Boolean weight encoding.

The first degree-37 planted PDP pilot returned no model under its bounds, so
it gave no natural-yield or end-to-end claim. This smaller degree-9 run checks
whether the complete plumbing works and measures its cost where ordinary
queries can finish. It gives no scaling claim for degree 37, 53, or 131.

## Frozen instance and method

- Field: `GF(2^9)` in polynomial basis, modulus `0x211`.
- Curve: `y^2 + xy = x^3 + 1`, order `508 = 4 · 127`; subgroup generator
  `G = (173, 175)` of prime order 127.
- Factor base: both rational points above each normal-basis weight-two `x`,
  projected into the subgroup by multiplication by four. There are 36
  distinct usable projected points before folding and two signed Frobenius
  columns. The normal element is selected by a deterministic first-match
  search; its exact value, point set, digest, and orbit representatives are
  in each immutable candidate manifest.
- PDP: five weight-two normal-basis `x` inputs, three nonzero intermediate
  `x` rows, four left-associated Koblitz S3 equations, and rationality
  clauses. A single reusable CryptoMiniSat instance receives only the query
  target's nine `x` bits as assumptions. Its model becomes a relation only
  after a rational curve-group lift. Multiplication by four maps the lifted
  points into the factor base and removes the order-two ambiguity.
- Relations: ordinary known-scalar multiples of `G`, seed 61009, until the
  two-column matrix has full rank. Gaussian elimination recovers and checks
  both representative logs. The target is a previously unseen public point
  `Q = (474, 176)` with audit scalar 49. Rerandomized target queries use seed
  73009. Floyd rho uses seed 92009 on that same point.

The candidate IDs are
`IC1N9Ckb1fb36PDP5satRCsampleLAgaussTDdescentISO0hf326d0028e44` (FC) and
`IC1N9Ckb1fb36PDP5satRCsampleLAgaussTDdescentISO0hbf79fbc6f3e9` (unary).
The shared workload is `W0dc797a1138a`. Each arm has runs `R1` through
`R3`; the run directory contains its candidate manifest, workload record,
full receipt, and schema-v2 row. The [six-run summary](runs/summary.json) and
[rows](runs/all_runs.jsonl) keep failures and costs visible.

## Measured outcome

All six runs recovered scalar 49 and independently replayed `[49]G = Q`.
Every run collected two verified ordinary relations in two precomputation
queries, reached rank two, and solved the target in one PDP query. The
precomputation work is outside the primary online interval; its separate
stage times, query status mix, formula sizes, and memory are in each receipt.

| Variant | Median one-target IC online wall | Observed range | Median same-point rho online wall | Median rho/IC |
| --- | ---: | ---: | ---: | ---: |
| FC-Hamming | 154.094 ms | 150.533–231.825 ms | 0.478 ms | 0.00317× |
| Unary counter | 68.088 ms | 66.988–68.095 ms | 0.496 ms | 0.00740× |

The paired unary/FC online ratios were 0.435, 0.294, and 0.452 (median
0.435): **FC-Hamming was slower** on this frozen N9 target. The range records
run-to-run variation across three repeats of one target, not uncertainty
across the target population. Both methods are far slower than rho here.
The ordinary-query yield of 2/2 per run and the online target yield of 1/1
are small controls, not natural-yield estimates for larger fields.

The IC online clock starts at the first target-dependent rerandomization,
after factor-base, relation-log, and SAT-formula preparation. It stops after
the recovered scalar has been replayed by both the run arithmetic and the
separate reference arithmetic. Its exclusive target query, PDP, relation
check, descent, and recovery-check phases sum exactly to the online wall.
The rho clock starts at its first target-dependent walk computation and also
includes independent replay. Fixture scalar generation is outside both
intervals. The reusable setup and all relation queries are retained as
separate precomputation costs, not folded into the online speedup. Operation
counts and the complete cold-start total remain unknown.

## Reproduction and review

This job does not invoke Sage. The host run used Homebrew Python 3.14.7 and
`pycryptosat` 5.14.7 on macOS ARM64. In an environment with `pycryptosat`
installed:

```sh
cd experiments/hamming-ic-e2e-20260929
python3 -m unittest discover -p 'test_*.py' -v
python3 run_e2e_n9.py --encoding fc --run-number 1 --out /tmp/new-n9-fc-r1
python3 verify_result.py /tmp/new-n9-fc-r1
python3 ../ic-candidate-catalog/analyze_v2.py runs/all_runs.jsonl
```

Choose a fresh output directory; run outputs are immutable. The exhaustive
Boolean check tests all 512 N9 masks against both exact-weight constraints.
The separate [verifier](verify_result.py) recomputes the factor base from
scratch with independent field and curve arithmetic, replays every retained
relation and target witness, checks both representative logs, the recovered
scalar, identifiers, source hashes, and exclusive timing. The candidate
manifest's source digests pin the exact producer code and native solver used
in each frozen run.
