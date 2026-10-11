# Step tables: group-operation experiment

This directory builds reproducible ECC2K-130 **synthetic** step tables and
measures finite collision work. The target is `Q = [65537]P`; the challenge
target, production runner, checkpoints, and collision pool are not used.

The delivered tables are valid arithmetic artifacts. **There is no confirmed
reduction in ECC2K-130 rho group operations or measured complete-walk GPU speedup
from this candidate.** The finite experiment supports further work on table walks, but
does not establish an improvement over the existing eight-branch table design.

A larger pair-sum artifact is now materialized under the requested 24 GB
budget: [pair128-24gb-20260921/README.md](pair128-24gb-20260921/README.md).
It contains 562,348,416 pair sums in 20,244,542,976 bytes, with checksums,
coefficient labels, a source snapshot, and independent arithmetic checks.
The pair-sum data does not by itself supply an intermediate branch predictor.

The larger [pair256-88gb-20260921 table](pair256-88gb-20260921/README.md) is
also materialized: 2,249,360,128 entries in 80,976,964,608 bytes, within an
88 GB budget. Its remapped overlap with the 128-branch table is checked.

## What is built

`table.py` constructs `T[h] = a[h]P + b[h]Q`, with independently derived nonzero
coefficients, deterministic rejection sampling, and rejection of duplicate
signed Frobenius orbits. Every entry is checked on the curve and against
`[a[h] + 65537*b[h]]P`; subgroup membership follows from the checked prime-order
generator. All 131 Frobenius conjugates are materialized. Signs are implicit.

The checked full-size artifact is `table32-20260921.json`:

* 32 base entries, 4,192 positive conjugates, 8,384 signed addends.
* Table identity SHA-256:
  `88b665d3a3d7c5b5e3e77996d7c6dbf14341003e11e63cb4ed9db25e01d6579c`.
* 12,317 group operations for table construction, with 6,060 additional
  independent audit operations recorded separately. Generator/target setup is
  not included in those two counts.
* A table identity identifies coordinates and coefficient labels. A full walk
  also needs a selector, selector salt, branch count, cycle rule, start rule,
  and distinguished-point rule; it must not use that table hash alone.

`pack.py` produces prefixes in `packed-20260921/`. Each entry is nine
little-endian 32-bit words in the polynomial basis
`z^131 + z^13 + z^2 + z + 1`: four low x words, four low y words, and
`x_top | (y_top << 3)`. Entries are ordered by Frobenius power, then branch.
Negation XORs x into y. The packer checks the basis matrices on all 131 basis
vectors and verifies both signs of every coordinate round trip.

| File | Branches | Positive addends | Coordinate bytes |
| --- | ---: | ---: | ---: |
| `packed-20260921/table8.bin` | 8 | 1,048 | 37,728 |
| `packed-20260921/table16.bin` | 16 | 2,096 | 75,456 |
| `packed-20260921/table32.bin` | 32 | 4,192 | 150,912 |

These sizes exclude selector data and coefficients. The 16/32-branch addends
already exceed the existing kernel's 48 KiB shared-table budget. They need a
different memory placement. The existing tag format has only four branch
bits, so 32 branches also need a new tag/checkpoint format. These binaries
match the **coordinate layout**, not the current walk identity or full table
buffer. The field representation also differs: these artifacts use
`z^131+z^13+z^2+z+1`, whereas the fast packed client's `packedtransform131.h`
uses its own optimal polynomial basis. Equal nine-word layouts do not make
those field coordinates interchangeable. They are not drop-in production tables.

The native [Metal walk](../../metal/README.md) runs the point-dependent
single-step recurrence against the compact signed-direction table. It does not
load the pair-sum payload or claim that two updates have been combined.

## Selector and operation savings

The existing weight selector is `h = (HW(x)/2) mod H`. Increasing H without
changing that selector does not create uniform choices. Under the
uniform-even-weight-word model at m=131, `1/sum(p[h]^2)` is approximately
7.902, 10.145, 10.153, 10.153 at H=8,16,32,64. This is a distribution model,
not a measured distribution of points on the actual subgroup.

The candidate uses an orbit fingerprint. If L(i) is the cyclic index of
normal-basis coordinate i, put

```
w = HW(x)
k = sum(L(i) * x[i]) / w mod m
u = rotate_right(cyclic_coordinates(x), k)
h = fold_mix64(u, salt) & (H - 1)
```

Frobenius adds one to every occupied cyclic index, so k increases by one and
u stays unchanged. Negation leaves x unchanged. A y bit at the highest
occupied position of u selects the addend sign; it flips under negation.
The step is

```
R' = R + (-1)^eps * Frobenius^k(T[h]).
```

Both the point and its `(a,b)` labels therefore transform correctly under
signed Frobenius. `Selector` is the reference implementation and the Metal
kernel evaluates the same selector from every current point. Use
`salt=record['seed']` when reproducing the finite experiment's convention.

There is still **one point addition per update**. A larger addend is not more
independent rho samples. A pair-sum table cannot skip two existing updates
without determining the second branch from the intermediate point. The aim
here is fewer additions **until a useful collision**, not relabeling one
update as several steps. Cheon, Hong and Kim's
[tag-tracing paper](https://www.math.snu.ac.kr/~jhcheon/publications/2008/TTDLP_A08_CheonHongKim.pdf)
studies finite-field multiplicative groups and explicitly leaves extending
its technique to elliptic curves as further work.

The published [ECC2K-130 walk analysis](https://ecc-challenge.info/anon.pdf),
Appendix B, explains the effect of unequal branch probabilities on its
Frobenius walk. Its estimates do not prove a collision constant for this
history-dependent adding walk.

## Executed experiment

`bench.cpp` uses complete affine arithmetic over GF(2^23), independently of
the Python normal-basis table generator. The subgroup order is 2,095,853;
there are 45,562 nonzero signed Frobenius orbits. The target scalar is public
and used to check labels, never to select a branch.

Each trial interleaves eight independent starts and retains every visited
orbit. Multiple starts are necessary: a single multiplicative Frobenius
trail cannot produce an independent relation with itself. Equal normalized
points count only when their normalized b coefficients differ and their
planted group equations agree. Infinity and fruitless returns trigger a
charged restart. All eight final states are checked against their full
coefficient equations. The two-/four-step history rule from the existing
table design is applied to every table variant.

Two separate experiments completed:

* `screen-20260921/result.json`: 8 table seeds x 256 trials x 7 modes = 14,336
  rows, seeds starting at 20260921.
* `confirm-20260921/result.json`: 16 fresh table seeds x 512 trials x 7 modes
  = 57,344 rows, seeds starting at 20261021.

All 71,680 trials produced a useful collision, with no censored trials or
exceptional termination. Raw trial rows, synthetic tables, exact compiler
command, source/binary hashes and platform information are retained alongside
each result. `weight8`/`weight16` reproduce the existing selector/cycle-rule
design with newly generated synthetic coefficients; they are not the exact
production binary or its table. The checked-in raw JSONL rows use deterministic
gzip compression to keep the review artifact bounded.

Fresh-seed confirmation (8,192 trials per mode):

| Walk | Mean walk additions | Mean charged group operations |
| --- | ---: | ---: |
| Legacy Frobenius | 323.456 | 562.074 |
| Weight table, 8 branches | 268.341 | 505.230 |
| Orbit table, 8 branches | 264.973 | 501.862 |
| Weight table, 16 branches | 263.024 | 500.847 |
| Orbit table, 16 branches | 259.598 | 497.421 |
| Orbit table, 32 branches | 265.749 | 505.445 |
| Orbit table, 64 branches | 265.090 | 508.539 |

Charged work includes walk operations, all initial/restart scalar
multiplications, and table construction amortized over the trial count.
Independent validation arithmetic is excluded. This is a group-operation
metric; it excludes field/basis/selection work and therefore is not a runtime
speedup measurement.

Against weight8, orbit8's charged-work ratio is 0.9933 with a table-seed
cluster-bootstrap 95% interval of [0.9753, 1.0115]. Orbit16's ratio is 0.9845
with [0.9692, 1.0011]. All orbit candidates' intervals overlap 1. **The new
selector/table sizes have not shown a confirmed gain over weight8.** The
lowest observed mean changed between screening and confirmation. A larger
table is not justified by these results alone.

The legacy comparison is favorable in this finite model, but its weight
distribution at m=23 has only about 4.3 effective branches. It cannot be
extrapolated to m=131, where the corresponding word model has about 7.9.
The table walk is near the finite ideal birthday mean of 267.523 updates;
that observation is not a proof of large-curve mixing.

## Reproduce

From this directory:

```sh
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 table.py --branches 32 --out table32-new.json
python3 pack.py table32-new.json --out packed-new
python3 run.py --out screen-new --table-seeds 8 --trials 256
python3 run.py --out confirm-new --table-seeds 16 --trials 512 --seed 20261021
```

Output paths must be new. `run.py` needs Python 3 and a C++17 compiler
(`--cxx` selects one). No cloud account, CUDA compiler, GPU or network service
is needed. Reference CPU timings must not be compared to the GPU engine.

## Remaining research questions

1. Implement and measure a correct intermediate selector before enabling pair
   sums in a walk. The current Metal kernel deliberately executes one ordinary
   addition per point-dependent update.
2. Resolve distributed trail coalescence before considering a new campaign.
   History-based avoidance depends on more than the current point; equal
   point orbits alone do not prove that subsequent trails will remain merged.
   The all-points experiment deliberately does not claim distinguished-point
   collection behavior.
3. Measure complete collection work with independent table seeds and charged
   setup, rare exceptions, cycle handling, report/replay cost and censoring.
   Full-size table arithmetic checks are not full-size collision evidence.

The existing production Frobenius walk and archived table-walk measurements
remain separate from these new synthetic artifacts.
