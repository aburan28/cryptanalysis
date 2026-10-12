# Preliminary S6 / Boolean descent size check

This exploratory check used the first **ordinary** n=83 target in the frozen
`manifest.json`, on the full l=17 x-subspace encoding (five 17-bit variables,
85 Boolean input bits). It is separate from the preregistered pair-table
pilot in `run-1/`. No five-summand solution or relation was obtained.

**Target correction for any future solver:** this diagnostic substituted the
projected target `R.x` only to measure construction size. The archived factor
base stores `[4]P` for original points whose x-coordinate lies in the
subspace. A valid original-point equation must instead target one of the four
preimages `T+K` of `R`, where `T=[4^{-1} mod r]R` and
`K ∈ {O,(0,1),(1,0),(1,1)}` is the rational 4-torsion kernel. Using `R.x`
with original x-variables is **not** a correct projected-base relation
encoding. Every extracted witness needs an exact `[4]sum(P_i)=R` replay.

Python 3.12.14 on x86_64 Linux, with a 512 MiB `RLIMIT_AS` and a 30-second
external watchdog: generating the characteristic-two S6 polynomial via
`sumpoly.summation_polynomials(6)` produced **190,252 monomials** in
**5.394 s** and had reached **458,608 KiB peak RSS**. Calling the existing
`descend.descend(S, F, E, 5, 17, xR)` on the same process did not return
before the 30-second watchdog exited with code **124**. The descent size,
solving degree, and result are unknown. This time is not a solver benchmark.

Source SHA-256: `sumpoly.py` =
`a13f3239ff09cd9a1b39f201aab3d2232fa5c7c48de450cf79accf2e330e96b5`;
`descend.py` =
`5fd60a1eb273f14ef6df363ca8b8ce06cadd33f6ec43f465b0048a095c6dba34`.
Frozen manifest SHA-256 =
`6eb9b081de664310a43349b2b2980163ae6e5cde7d4f916cc627e425baab78d6`.

Reproduce without creating a cache file:

```sh
timeout 30s python -u - <<'PY'
import json, resource, sys, time
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
sys.path.insert(0, 'experiments/pdp-scaling')
import sumpoly, descend
from gf2n import GF2n, Curve
case = json.load(open('experiments/pdp-scaling/five-sum-20260928/manifest.json'))['cases'][1]
field = GF2n(83, int(case['modulus']))
start = time.monotonic()
polynomials = sumpoly.summation_polynomials(6)
print('S6', len(polynomials[6]), time.monotonic() - start,
      resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, flush=True)
result = descend.descend(polynomials, field, Curve(field, 1), 5, 17,
                         int(case['queries'][0]['target'][0], 16))
print('descent', len(result), time.monotonic() - start)
PY
```

The next controlled engineering step is a bounded descent that streams or
factors S6 coefficients so construction and Boolean equations share a fixed
memory budget. A successful encoding must then solve and independently replay
ordinary full-base relations before any claim about relation throughput.
