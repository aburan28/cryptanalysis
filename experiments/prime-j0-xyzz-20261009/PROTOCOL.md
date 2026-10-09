# XYZZ accumulation screen for fixed-base unit-orbit tables

Retaining `ZZ=Z²` and `ZZZ=Z³` between mixed additions gives an arithmetic
path for the U14 and radix-943 table formats without changing their digit
selection or retained point tables. For affine addend `(x₂,y₂)`, the generic
XYZZ formula uses **8 field multiplications and 2 squares**; the current
Jacobian path uses eleven field products when a square is charged as a
product. The final conversion uses one inversion, three multiplications,
and one square in both representations. The XYZZ formula and count are
recorded in the [Explicit-Formulas Database](https://hyperelliptic.org/EFD/g1p/auto-shortw-xyzz.html).

This is an implementation candidate for the existing scalar schemes. The
coordinate formula is established prior work. Its benefit in this codebase
depends on the cost of another live `Pair` coordinate, balancing, memory
traffic, exceptional handling, and the complete online interval.

## Frozen mathematical check

Commit this protocol and `xyzz_formula_check.py` before running the panel.
The deterministic input law uses Python `Random(20261009)` and 64 sequences
of fourteen independent 256-bit scalar draws reduced modulo the secp256k1
group order. Convert each scalar to a public point with the independent
affine double-and-add path in `lazy_tau_screen.py`. After every XYZZ mixed
addition, compare its affine output to the independent affine group sum and
check `ZZ³=ZZZ²` modulo `p`. Preserve the input digest and every status in
the result. Also check identity, equal-point doubling, inverse pairs, and
the same exceptional cases after the accumulator becomes nonaffine.

The generic formula is

```
U = x₂ ZZ         S = y₂ ZZZ
H = U - X         R = S - Y
HH = H²           HHH = H HH         V = X HH
X' = R² - HHH - 2V
Y' = R(V - X') - Y HHH
ZZ' = ZZ HH       ZZZ' = ZZZ HHH
```

For `H=0`, `R=0` selects XYZZ doubling; `H=0`, `R≠0` selects identity.
For `a=0`, the doubling fallback costs `6M+3S` with the formula checked in
the source. The symbolic operation count is a stage diagnostic, not a CPU
timing ratio. Native integration must preserve the exceptional behavior and
be paired against the current Jacobian path on identical inputs and memory.
