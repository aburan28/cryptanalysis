# Q1506: base weight alone leaves the independent first-pair scan near 2^123.289

The Q1505 deferred-y four-sign scan was priced against four degree-131
normal-basis weight bounds. W5 and W6 use Q1413's exact enumerated usable
base sizes and signed-Frobenius column counts. W7 and W8 use Q1447's sampled
conditional projection counts and Wilson intervals. The curve is
`EC1N131Ckb1h6816f880945e`; no isogeny transport is specified.

| Weight bound | Base status | Usable points `B` | Folded columns `K` | One complete four-sign scan, batch mul log₂ | Four-sign match probability ceiling, log₂ | Expected `K` unordered-pair matches, batch mul log₂ under independent uniform first-pair model | Sparse matrix proxy, modular ops log₂ |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | exact | 309,633,434 | 1,181,807 | 31.528 | −71.588 | **123.288505089** | 42.345 |
| 6 | exact | 6,559,634,788 | 25,036,774 | 35.933 | −62.778 | **123.288505093** | 51.155 |
| 7 | sampled conditional | 118,153,819,312 | 450,968,776 | 40.104 | −54.436 | **123.288505093** | 59.497 |
| 8 | sampled conditional | 1,844,590,711,506 | 7,040,422,563 | 44.068 | −46.507 | **123.288505093** | 67.426 |

The scan model charges every complete four-sign scan, including failed
ones. For each uniform nonidentity query, a fixed first x-pair is chosen
independently of the target. The four signed complements together expose
at most four sets of `B(B+1)/2` unordered signed-base second-pair sums.
Their union bounds the chance of any match; linearity bounds the expected
number of signed-complement/unordered-pair matches by the same quantity,
including scans with multiple raw x-key hits. Each such match can add at
most one rank row. The resulting expected-work floor for `K` matches is
in [analysis.json](analysis.json).
All four rows have `B=262K`. The Lean-checked accounting identity is

`K(r−1)(10B)/(4(B(B+1)/2)) = (5(r−1)/(2n))·B/(B+1)` when `B=2nK`.

At `n=131`, `B/(B+1)` changes only in its last few decimal places across
these bases. A larger base makes each scan more expensive while increasing
the fixed-first-pair hit ceiling and required column count proportionally.
Its mean number of unordered four-point representations per uniform target
varies much more: the log₂ upper values are −20.761, −3.141, 13.543, and
29.401 for W5 through W8. This changes which relation collectors might
benefit from a larger base, but does not rescue the independent complete
scan route under the stated model.

The matrix column counts create another selection constraint. The table's
`4K²` sparse-scalar matrix proxy reaches `2^67.426` modular operation
events for conditional W8; it is a model, not a lower bound or a calibrated
field-multiplication conversion. W7's proxy is `2^59.497`, leaving little
room under an abstract `2^61` modular-operation cap for other stages if
that model applies. Exact W5/W6 counts have much smaller matrix proxies,
but their ordinary relation yield with a guided solver remains unmeasured.
The conditional W7/W8 interval endpoints, batch-inversion counts at 128,
512, 2048 and 8192 pairs, and all exact input hashes are retained in
[analysis.json](analysis.json).

The result narrows the next solver target: reduce the number of complete
second-pair scans per useful relation by selecting first pairs using the
target or by indexing second-pair sums. Measure ordinary N53 and N83
verified yield and novel rank before extrapolating that method. The
fully charged N131 solve exponent remains null, and no challenge dispatch
is authorized by this stage model.

The [protocol](protocol.json), [calculator](analyze.py),
[formalization map](FORMALIZATION.md), and [read-only validator](validate.py)
freeze and check the sweep. Run:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n131_weight_scan_surface/validate.py
```
