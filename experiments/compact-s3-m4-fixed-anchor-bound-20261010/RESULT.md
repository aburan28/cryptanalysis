# Fixed-anchor four-sum work bound on the exact N53, N83, and N131 bases

A target-independent left-pair schedule needs at least **`2^117.89`
rational-root visits** at N131 to reach a 95% full-rank chance for a
relation-query stream with uniform nonidentity subgroup marginals, even when
each complete scan can test eight fixed signed left sums and every
right-pair representation adds rank. The exact W≤5 and W≤6 N131 factor
bases give this same root-visit exponent to better than one part per million.
This identifies target-adaptive
left-output generation as the necessary algorithmic change for this
complete-scan family; changing only the sparse-weight cutoff or inversion
window does not remove its rank-work barrier.

This is proposal `Q20261010123500`, with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"` (`ISO0`). It is an exact conditional rank-work
calculation. The
[frozen protocol](PROTOCOL.md), [freeze](freeze.json),
[integer calculator](bound.py), [result](result.json), and
[independent minimality audit](audit.json) retain the input law, exact base
receipts, source hashes, branch allowances, and all twelve integer rows.

## Rank-work argument

Let the subgroup have prime order `r`, the actual usable base have `B`
points and `K` folded columns, and a complete fixed-output scan visit `D`
rational raw-`x` coordinates. Assign scans to query points `Q_i`, each with
a uniform nonidentity subgroup marginal. Fix the entire left-sum schedule
and query assignment independently of the joint query vector. The queries
may be correlated. Permit up to `h` signed left
subgroup sums per scan, with `h=1,2,8` computed separately. For each such
sum there are at most `M=B(B+1)/2` unordered right-point pairs, including
repeats. Each signed-left/right-pair combination equals at most one assigned
query point. Thus `S` complete scans yield at most `S h M/(r−1)` expected
representations, whether the scans' left sums are correlated or not. Novel
rank is no greater than the number of representations, so Markov's
inequality gives the necessary 95% condition

```text
S >= ceil(19 K (r−1) / (20 h M)),
root visits >= S D.
```

The four exact base receipts all give `D=B/2=nK`: each rational raw-`x`
Frobenius orbit has length `n`, and both point signs contribute to `B`.
Substituting this identity shows that the root-visit product approaches
`0.95(r−1)/(2hn)` as `B` grows. The code uses exact integers, so no
asymptotic approximation enters the reported rows. The independent auditor
recomputes `M` with `math.comb`, checks that one fewer scan fails the 95%
necessary threshold, and verifies the W≤5/W≤6 equality to within one part
per million.

| Exact base and curve | Actual `B` / folded `K` | `h=1` scans, log₂ | `h=1` root visits, log₂ | `h=8` root visits, log₂ |
| --- | ---: | ---: | ---: | ---: |
| N53 Q1301 W≤3, `EC1N53Ckb1hf77aab617904` | 24,062 / 227 | 23.90 | **37.46** | 34.46 |
| N83 Q1325 W≤5, `EC1N83Ckb1h876c2921cb64` | 30,977,592 / 186,612 | 49.67 | **73.55** | 70.55 |
| N131 Q1413 W≤5, `EC1N131Ckb1h6816f880945e` | 309,633,434 / 1,181,807 | 93.69 | **120.89** | **117.89** |
| N131 Q1413 W≤6, same curve | 6,559,634,788 / 25,036,774 | 89.28 | **120.89** | **117.89** |

The `h=8` row is a conservative **assumed allowance**, not a measured count
of branches in another producer. If a fixed-output implementation tests no
more than eight predeclared signed left sums per scan, its conditional work
obeys that row. A query-selected left sum or a schedule adapted after
earlier scan results requires separate analysis. A fixed public target also
requires separate evidence: uniform-marginal probability statements do not
decide its individual decomposability. The relation-query scans belong to
target-independent preparation when computing a one-target online time.

## Relation to the measured S3 kernel

The [rational-orbit scan](../compact-s3-m4-rational-root-scan-20261010/RESULT.md)
measured `92,942,180 / 15,488,796 = 6.0006` field multiplications per
rational N83 root visit at its 4,096 window. Carrying that **measured stage
ratio** to N131 gives `2^120.48` field multiplications for the `h=8` W≤6
row. This is an extrapolation for that literal scan kernel; the theorem's
independent unit is root visits. Its conservative `h=8` N131 visit count
is **56.89 bits above `2^61` in that unit**. The exact base digests and
subgroup orders are saved in [result.json](result.json), and the source
kernel digest is bound by [freeze.json](freeze.json).

The earlier `2^61.84` N131 field-multiplication screen assumed only one
full rational scan per Q1414 uniform subgroup query while optimistically
crediting every possible four-point representation and every row as novel.
This fixed-anchor calculation adds the missing number of scans needed to
*find* right pairs from a predeclared left schedule. Neither figure is a
complete cold or one-target online solve exponent; both remain `null` in
the machine-readable result. The N53 ordinary relation obtained by the
separate pair index uses a reusable multi-pair table, so its search is not
modeled as this one-left-sum complete scan.

## Next algorithm experiment

Construct left pair outputs *jointly with the target* before asking the
right-pair oracle. Freeze the same exact N53 and N83 ordinary points and
bases, record every generated output and failed probe, and measure verified
relation yield and novel rank per charged group or field operation. A
passing design must give a source-bound N131 output-generation cost and
bounded memory; the four-sum scan can remain an exact terminal witness
checker. Only a complete relation, matrix, and target-descent accounting
can assign the challenge-size solve exponent.

The first freeze in [v1](v1/) used one repeated uniform query point for all
scans. It was superseded before publication because the rank question is
about a stream of relation queries. The current freeze uses uniform
marginals for each assigned query and a schedule independent of their joint
vector; the integer rows are unchanged.
