# Packed Boolean separator elimination for S3 chains

This experiment implements exact Boolean factor elimination with packed
satisfying-assignment tables. It evaluates each ANF equation by a Boolean
Möbius transform, joins factors in the current elimination bag, existentially
projects one variable, and records a witness bit for reconstruction. A
completed assignment is checked again against every original ANF equation.
The prototype bounds each bag to 24 variables and charges factor construction
and elimination against a combined state cap of at most 200 million. It returns explicit
`width-cap` and `state-cap` statuses; those statuses are retained as unknown
results rather than interpreted as unsatisfiability.

For an equation scope of size `s`, table construction uses `O(s 2^s)` byte
XORs and `2^s/8` packed factor bytes. A joined bag of size `w` uses
`O(2^w b)` membership tests for `b` factors, plus packed projection and a
witness table of at most `2^(w-1)/8` bytes. The implementation records those
counts, the maximum live packed-factor words, and every returned width. The
S3 auxiliary-coordinate chain has an explicit order bounded by `2n+ell` for
`m>=4`, as proved in the predecessor
[separator study](../groebner-f6-20261008/README.md). The packed representation
tests that bound at `n=9`, `ell=3`, where the middle link has width 21.

The positive-control panel rebuilds the exact planted S3 chain at
`m=3,4,5,6` and checks optimized and UBSan results against the original
equations. The separate semantic screen enumerates all point sums from the
`n=9`, `ell=3`, `m=4` factor-base points, then solves every frozen target
abscissa. It first records a concrete S3-only satisfying assignment for an
unreachable target. It adds one block-local ANF equation per summand and
intermediate abscissa to require a curve point lift; these unary constraints
preserve the 21-variable width bound. Every satisfying assignment is then
replayed with actual curve-point choices and finite intermediate sums.

Run the frozen experiment with:

```sh
python3 experiments/groebner-f6-packed-20261009/build.py
python3 experiments/groebner-f6-packed-20261009/test_packed.py
python3 experiments/groebner-f6-packed-20261009/panel.py --output /absolute/panel-directory
python3 experiments/groebner-f6-packed-20261009/semantic_screen.py --output /absolute/semantic-report.json
```

The 245 small random Boolean systems have an exhaustive oracle. The packed
S3 panel and semantic screen are structural and correctness experiments, not
IC online timing measurements. The next hybrid algorithm experiment should
replace a large local table by a proof-carrying F4/F5 projection while keeping
the same separator and point-lift checks. It must account for certificate
transport and actual ordinary-query yield.

The completed panel, semantic counterexample, and exact target census are in
[RESULTS.md](RESULTS.md), with raw records in [evidence](evidence/manifest.json).
