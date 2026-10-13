# Exact N83 two-coset width-13 factor-base optimum

The union of width-12 affine cosets at offsets **bits 37+73** and
**bits 12+51** has **4,349 signed-Frobenius columns** and **721,934
usable subgroup points**. It is an exact maximum among unions of any two
distinct two-coordinate offsets outside the frozen width-12 normal-basis
span. The union is an affine 13-dimensional subspace: if `W` is the
12-dimensional span and `a,b` are its two offsets, then the union is
`a + W + span_F2(a+b)`.
The machine-readable [affine basis manifest](basis_manifest.json) gives
the exact 13 normal-basis vectors, offset, orbit rule, and key digest.

| Exact factor-base geometry | Prior shifted width 13 | Best two-coset width 13 |
| --- | ---: | ---: |
| Affine `x` candidates | 8,192 | 8,192 |
| Signed-Frobenius columns `K` | 4,125 | **4,349** |
| Usable subgroup points `B=166K` | 684,750 | **721,934** |
| Full-base five-subset first moment `binom(B,5)/r` | 518.85137 | **675.88151** |

The 5.43% larger base raises the exact full-base five-subset first
moment by **30.26%**. This is a combinatorial geometry result; a
decomposition solver, ordinary-query relation yield, novel rank, and
single-target online cost for this base remain unmeasured. The extra
13th basis vector differs from the consecutive geometric basis, so
its point-decomposition circuit cost must be measured separately.
`candidate_id` remains null.

## Exhaustive two-coordinate screen

The checked [screen protocol](protocol.json) fixes the Koblitz curve
`y^2+xy=x^3+1` over `GF(2^83)`, its prime-order subgroup, the type-II
normal basis, and `W=span_F2(gamma_1,...,gamma_12)`. It screens all
**2,485** two-coordinate offsets `gamma_i+gamma_j` with
`12 <= i < j <= 82`. Each of their 4,096 affine `x` values is tested
by the exact lift condition `Tr(x+1/x)=0`. The
[screen](screen.json) and [progress ledger](screen.progress.jsonl)
retain every lift count.

The best individual coset is bits **37+73** with 2,196 rational lifts,
2,196 folded columns, and 364,536 usable points. The runner-up by
lift count is bits **12+51** with 2,156 lifts and 2,155 columns; one
seed repeats an orbit key. The best cosets share **two** orbit keys,
so their union has `2196+2155-2=4349` columns. The
[union protocol](union_protocol.json), [result](union.json), and
[complete sorted key file](union_keys.bin) retain those details.
The original top-pair attempt assumed zero duplicates, failed at that
assertion, and is preserved as [source](union_attempt1.py),
[protocol](union_attempt1_protocol.json), and
[failure receipt](union_attempt1.stderr.txt). The corrected producer
uses exact set union and lift-count branch-and-bound.

The result is a **global maximum within this two-coset family**.
Any pair other than the top two has at most
`2196+2150=4346` rational lifts, because 2,150 is the third-largest
count. Each folded column needs at least one rational seed, so every
other pair has at most 4,346 columns, below the measured 4,349.
The largest individual coset is unique as well: the next lift count
is only 2,156. The [Lean module](LiftBound.lean) checks these two
conditional counting implications; the [axiom audit](lean-build.txt)
reports no axioms. The specific 2,485 finite-field lift counts and
the curve-orbit bridge are computationally verified and remain outside
the Lean formalization.

The independent [Sage screen replay](independent_sage_replay.json)
recomputes every lift count in a polynomial field and checks all
winner points, subgroup projection, and normal-basis keys. The
[independent union replay](independent_union_sage_replay.json) checks
both cosets, their key intersection, full union key bytes, and the
all-pair upper bound. Both replays construct rational points with the
exact odd-degree half-trace Artin-Schreier formula and check the curve
equation. Earlier attempts using Sage's generic per-seed `lift_x` were
stopped in that slow lifting phase; the [interruption receipt](interrupted_verification.json)
preserves their source hashes and last progress. The checked
[Sage runtime identity](sage_runtime_info.json)
was saved before the producers. These construction times ran on a
shared local host and are exploratory diagnostics only.

The [read-only audit](verify.py) checks source and input hashes,
all screen rows, prior base counts, exact keys, both independent Sage
replays, and Lean output:

```sh
python3 experiments/n83-geometric-two-shift12-20261012/verify.py
```

The next end-to-end test should build an orbit-complete five-summand
decomposition circuit for this affine width-13 basis and pair it with
the prior shifted width-13 arm on the same public point and resource
envelope. It must measure verified ordinary relations, novel rank,
factor-base logs, final matrix work, target descent, and same-point
rho before an online speed claim.
