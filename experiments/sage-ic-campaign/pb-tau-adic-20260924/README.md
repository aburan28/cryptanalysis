# Polynomial-basis Koblitz Frobenius scalar multiplication

Both local and tracked runner `CurvePb.mul` copies now use the exact
`tau² + tau + 2 = 0` Frobenius relation for scalars of at least eight bits
on `y² + xy = x³ + 1`. Smaller scalars keep the existing binary loop.
This matters for the runner's `NormalView.pb` path when an optimal normal
basis is unavailable. The preceding ONB change is separate.

`baseline/` and `source/` freeze the exact files. Primary and confirmation
intents were frozen before measurement and bind code hashes and independent
input seeds. Each of twenty fresh-process cells records separate first
calls and twelve alternating warm full scalar calls. Outputs were checked
against the parent and for curve membership. The exact test covers both
local and runner copies, all points on small even and odd degree fields,
order-two and infinity behavior, negative scalars, and long scalars.

Portable archive verification:

```sh
python3 experiments/sage-ic-campaign/pb-tau-adic-20260924/verify_archive.py
```

With isolated `python-sat` and `pycryptosat` dependencies, 29 of 30 broader
runner unit tests passed. The remaining test requires an
`ecc2k130-fixed.json` fixture absent from this checkout. The log is
archived. See `RESULT.md` for measured scope.
