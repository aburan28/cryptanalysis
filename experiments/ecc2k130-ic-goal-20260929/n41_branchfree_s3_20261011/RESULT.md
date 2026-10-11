# Branch-free S3 and guarded target constants on the N41 W9 public point

**An exact reciprocal-coordinate S3 rewrite removes the auxiliary Artin–Schreier branch bits, and a guarded four-preimage final link reduces the W9 public-query formula by 705 AND gates, 1,999 clauses, 300 native XOR rows, and 32,408 bytes relative to the frozen halftrace circuit.** The complete positive assignments pass both new circuits. Under the same one-worker, 120-second solver and 4-GiB memory envelope, both unpinned public-point searches ended `BOUNDED_UNKNOWN` with active CryptoMiniSat search.

## Exact encoding

For a reciprocal S3 link with coordinates `a,b,c` in characteristic two, set `w=abc` and `X=a+b+c`. The cleared S3 equation is `X²=w²+w`. Squaring is a field automorphism, so it is equivalent to

`a+b+c = w + sqrt(w)`.

The square-root map is binary-linear. At each source-pair leaf, use `X=s+c` and `w=pc`, where `s` and `p` are the exact sum and product of its two source masks. The pair and middle links retain their multiplication gates and the exact rational mask and distinct-column rules. The [independent field check](identity_check.json) confirms all seven links of the frozen assignment and matches the cleared S3 predicate on 1,024 deterministic field triples; the algebraic equivalence applies to every field triple.

The second variant shares `v=middle₀·middle₁` at the final link. For each of the four public-target raw preimage reciprocals `z_i`, it computes `w_i=z_i v` with a constant binary-linear map and guards the corresponding 41 output equations with the two target flags. This retains all four target branches in one formula. The [full-formula control](guarded/full_assignment.json) passes the known assignment at its correct flag setting; holding the assignment fixed at the other three flags violates 21, 19, and 21 clauses.

## Frozen W9 public-query panel

The curve is `EC1N41Ckb1h023d9a38bbf7` over `GF(2)[t]/(t^41+t³+1)`, with subgroup order `549756390943`. The original public point is `(1458168294740,1672312028033)` and its transported point is `(920359962848,755404565011)`. The four same-rotation source pairs use W9 and rotations `0,10,20,30`. Independent geometry enumeration established **B=2,072 distinct signed factor-base points** and **251 folded columns**. The archived W9 positive control and public-query receipt are the exact comparator.

| Same W9 point and four target preimages | Variables | AND gates | Clauses | XOR rows | XCNF bytes | Solver interval | Peak combined RSS | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Halftrace | 16,188 | 9,431 | 29,301 | 6,430 | 863,532 | 125.193 s | 94,388,224 B | `BOUNDED_UNKNOWN` |
| Branch-free | 15,912 | 9,431 | 29,294 | 6,161 | 839,301 | 125.129 s | 100,630,528 B | `BOUNDED_UNKNOWN` |
| Branch-free and guarded constants | 15,176 | 8,726 | 27,302 | 6,130 | 831,124 | 125.057 s | 82,526,208 B | `BOUNDED_UNKNOWN` |

Each new query froze its source and input hashes before control and search, used one CryptoMiniSat thread with `--xor=0 --random=20261011 --maxtime=120`, and had a 125-second parent stop and 4-GiB combined RSS ceiling. The solver logs contain 1,197 and 744 active restart lines for the new variants. Their exclusive construction/write/solver intervals and log hashes are in their `query/query_result.json` receipts. The [terminal audit](audit.json) checks source and target binding, complete positive assignment counts, four-target guard control, active capped solver status, phase sums, RSS, and compressed log hashes. Local wall and RSS differences are exploratory; both searches reached their cap, so these rows establish formula-size improvements and bounded search outcomes.

## Next method test

Use the guarded final link as the smaller exact target-coupled core, then add a multiplication-aware constraint that can reject two-pair source families before all eight masks are selected. Measure whole-family rejection, construction cost, solver work, and exact group replay on the same unpinned N41 point. A corresponding N131 public query still requires a source-bound full-work projection within one worker, 600 seconds, and 4 GiB.

Replay the receipts with `python3 -B experiments/ecc2k130-ic-goal-20260929/n41_branchfree_s3_20261011/identity_check.py`, the `freeze`, `control`, and `query` modes of each variant's `run.py` in a fresh output directory, `guarded/control_full.py`, and `audit.py`. Existing query receipts are write-once records and should not be overwritten.
