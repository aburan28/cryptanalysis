# Result: curve square terms through ONB Frobenius

The accepted curve source is SHA-256
`d7ccabe5688f4706b972a1c6508e7316f4c478e2fb2437e735734a4c6ee9d8d0`.
The field source is unchanged from the Python 3.9-compatible parent,
SHA-256 `191584f34e0092922cf8747d075a0791df702b6153923285b48736d96b0c6c03`.
In the binary ONB model, squaring is the Frobenius permutation already
implemented by `Onb.sqr`; six general-multiplication square terms across four
curve methods now call it.

| Degree 131 warm operation | Paired run A | Paired run B |
| --- | ---: | ---: |
| `Onb.sqr` unchanged control | 1.046× | 0.955× |
| `Curve.onCurve` | 1.73× | 1.30× |
| `Curve.dbl` | 1.67× | 1.72× |
| `Curve.add` | 1.45× | 1.07× |
| `Curve.pointFromX` | 1.30× | 1.45× |
| `Curve.mul(P, 17)` | 1.29× | 1.18× |

The degree-5 and degree-9 unchanged `Onb.sqr` controls stayed within 0.99–1.00×.
The benchmark used identical seeded inputs, 11 alternating matched rounds for
curve operations, and 8 repeats per round. Ratios are medians of old/new
ratios within each round. Exact field and curve outputs matched in every run.

The **first** `Curve.dbl` on a fresh degree-131 field is slower: seven fresh
processes per side gave median **1.766 ms candidate versus 0.094 ms incumbent**.
The candidate constructs the exponent-1 Frobenius table on that call. The
warm paired doubling runs saved about 55–83 μs per call, giving a diagnostic
break-even of roughly **21–31 doublings** for this isolated stage. Cold table
construction must be charged once to setup in any complete IC comparison.

`verify_v3.py` matched **1,080** original square and curve outputs across
degrees 5, 9, and 131, including point recovery, exceptional additions,
doubling, point validation, and scalar multiplication. It passed under
Python 3.9 and 3.13. Five local IC tests and 14 Python 3.9 artifact replay
tests passed with the candidate branch.

The first candidate also simplified `Onb.sqr`, but its degree-131 field-square
gate failed; that source and its timings are retained. The accepted change
uses the existing field method. These are local Apple Silicon CPU stage
results. The Python ONB path does not use Metal. A complete IC or DLP speedup
is **unknown** because the SAT-backed full runner is unavailable here and no
calibrated common operation-unit recovered-log comparison was made.
