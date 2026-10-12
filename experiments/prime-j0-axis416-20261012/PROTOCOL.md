# Axis-factorized radix-416 scalar format

This format evaluates fixed-generator secp256k1 scalars through thirteen
Eisenstein radix-416 windows and two terminal axis lookups. Its input law
is the frozen 4,096-scalar panel in
`experiments/prime-j0-sector-digit-20261010/fresh-inputs.json`; `screen.py`
uses the same nearest representative and the radix-569 design rows as a
matched structural control. The scalar subgroup order, generator, and
endomorphism eigenvalue are those pinned by the imported secp256k1 modules.

For each scalar, take its nearest Eisenstein representative `z=(a,b)` and
perform thirteen nearest four-corner digit steps with integer radix 416.
The terminal pair `t` has `3Q(t)≤927429454` for
`Q(a,b)=a²+3ab+3b²`. Rotate each nonzero `t` into the unique six-unit
sector `(-u,b)` with `u≤3b<2u`. Its exact factorization is
`(-u,b)=(-u,0)+(0,b)`. Store `u` points on the first terminal axis and
`b` points on the second, then apply the recorded unit to both terms.
The two axis point tables have 35,164 and 23,442 entries; zero is implicit.

`search.py` evaluates the exact thirteen-window point-entry formula for
every integer radix from 350 through 450. Monotone terminal bounds exclude
radices 2 through 350, and the ordinary table count excludes all radices
450 and above. This proves the unique minimum at 416 for this specified
thirteen-window, two-axis construction and its universal bound.

The first frozen phase consists of `search.py`, `axis.py`, `screen.py`, the
Lean theorem modules, `check.py`, and their outputs. A holdout generator
must be committed after this phase; its replay source must be committed
before drawing any new holdout inputs. Independent point replay and a native
implementation are separate gates. CPU timing requires a qualifying
isolated-host receipt and a matched complete-operation comparison.
