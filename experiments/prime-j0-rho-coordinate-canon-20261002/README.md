# Oriented sixfold rho walk on prime-field j=0 curves

This experiment changes the **rho walk** on `y^2 = x^3 + b` over a prime
field with `p = 1 (mod 3)`. It composes with the tau-adic scalar setup from
the [Xu–Yu–Han–Lu experiment](../prime-j0-tau-20260930/README.md): both
paired builds below use the same width-2 tau setup. The changed walk is now
the default for the library's j=0 GLV solver. Set
`CA_J0_RHO_COVARIANT_WALK=OFF` to select the former walk.

**Measurement status:** The wall ratios below are exploratory because the
ARM64 host was heavily contended and had no exclusive CPU/NUMA partition.
They need replay through the [isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md)
before serving as controlled speedup claims.

## Walk construction

Write `psi(x,y) = (beta*x,-y)` and `psi(P) = [lambda]P` on the selected
prime-order subgroup. For a nonidentity subgroup point, the sixfold orbit
has x coordinates `x, beta*x, beta^2*x` and y coordinates `y, -y`.
The minimum encoded x and y define a deterministic representative `C`.
The value `min(y,p-y)` in Montgomery encoding labels the whole orbit; after
mixing, it gives an orbit-invariant jump partition and distinguished-point
predicate.

Suppose the walking point is `Y = psi^e(C)`. For jump
`M_i = alpha_i*G + beta_i*Q`, precompute each `psi^e(M_i)` and its scalar
coefficients `lambda^e*(alpha_i,beta_i)`. The step is

```
Y' = Y + psi^e(M_i)
(a',b') = (a,b) + lambda^e*(alpha_i,beta_i)  (mod r)
```

The jump index is constant across the orbit, so this map satisfies
`F(psi(Y)) = psi(F(Y))` on the ordinary six-point classes. A class collision
therefore stays merged. At a distinguished point, the solver maps a copy of
`Y` to `C`, transports `(a,b)` by the matching power of `lambda`, inserts
the canonical hash and coefficients, and verifies any recovered scalar by
replaying `[x]G = Q`. The former walk applies the endomorphism and hashes
six representatives, then multiplies both coefficients, on every step.
The new walk uses two field multiplications to determine orientation and
normally updates coefficients by modular additions. It retains the former
look-ahead rule for fruitless two-cycles and the same walk count, jump count,
distinguished-point policy, single CPU thread, and batch point additions.
It expands the jump table by a factor of six, to at most 192 entries. This
implementation is our derivation; the general motivation and cycle issue
are discussed in [Bernstein–Lange–Schwabe](https://eprint.iacr.org/2011/003.pdf)
and [Wang–Zhang](https://eprint.iacr.org/2011/008.pdf).

## Frozen one-target panel

Each row below compares two fresh processes with empty distinguished-point
tables on **the same target point**. A target scalar is selected by SHA-256
of `j0-covariant-panel-v1:<curve>:<index>`, reduced to `[1,r-1]`, and used
only to construct the fixture point. The walk seed is `20261002`. Target
generation, curve setup, generator discovery, process launch, and input
loading are outside the clock. `online_ms` is the solver's wall interval
from entry to `ca_curve_solve`, including target-dependent jump construction,
all walk attempts, collision recovery, and its internal independent scalar
replay. A second fixture-scalar and point replay check is outside this
interval and is recorded as `verified=1`. `cpu_ms` measures process CPU time
over the same solver call and is a load diagnostic. The reference and
candidate each use width-2 tau setup, one CPU thread, identical curve and
seed, and the same resource policy. Run order alternates by target.

| Subgroup | Targets | Reference median online ms | Oriented median online ms | Median paired wall ratio | 95% bootstrap interval | Faster pairs | Median paired CPU ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| j0-36, `r=51131959441` | 64 | 18.703 | 6.920 | **2.785×** | 2.159–3.554 | 59/64 | 2.517× |
| j0-37, `r=157632877033` | 64 | 52.819 | 16.458 | **3.375×** | 2.197–4.992 | 56/64 | 3.101× |
| j0-46, `r=42111239174233` | 32 | 762.544 | 232.414 | **3.260×** | 2.677–4.240 | 31/32 | 3.183× |

`j0-37` is an existing fixture label; its displayed order has a 38-bit
binary length. The other orders have 36 and 46 bits, respectively.

All 320 solves recovered and independently verified the target log; there
were no timeouts or failed rows. The ratio column is the median of the
within-target ratios, so it need not equal the ratio of the two displayed
medians. The interval resamples target pairs 10,000 times with fixed seed
`20261002`. Individual rho collision paths vary: 14 of the 160 oriented
solves had higher wall time than their reference pair. The raw rows retain
both times, reported operation counts, distinguished-point entries, memory
estimates,
point coordinates, seeds, logs, and verification flags:
[j0-36](panel-j0-36-expanded.jsonl),
[j0-37](panel-j0-37-expanded.jsonl), and
[j0-46](panel-j0-46-expanded.jsonl).

The oriented walk's median operation count was higher in each panel
(142,429 versus 125,888 on j0-36; 223,319 versus 207,156 on j0-37;
3,775,260 versus 3,391,699 on j0-46). These counts include scalar setup
and omit some non-addition work, so the wall ratio is the performance metric.
The observed gain is consistent with a lower per-step constant cost;
the walk retains rho's square-root complexity. A coordinate-canonicalization-only
ablation on [12 j0-37 targets](panel-j0-37-coord-only.jsonl) had a 1.478×
median paired wall ratio and won 10/12 pairs. The larger covariant gain on
these targets is consistent with the oriented jump and coefficient update.
An exploratory [width-4 comparison](panel-j0-37-covariant-width4.jsonl)
had unstable wall timings under host load, so width 2 remains the default.

These are physical Darwin 25.6.0 ARM64 CPU measurements with Apple clang
17.0.0, Release builds, `CA_CUPQC=OFF`, and portable CPU arithmetic. The
host load average was roughly 47–70 during the expanded runs. Alternating
order and process CPU times support the result, but the wall ratios need
confirmation on an unloaded host. No x86-64, GPU, or 256-bit speedup is
claimed; this library's curve arithmetic uses 64-bit field elements.

## Reproduce

From the repository root, build both variants from the same source. The
reference flag is explicit because the oriented walk is now the default:

```sh
cmake -S . -B /tmp/j0-rho-reference -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_WERROR=ON -DCA_J0_RHO_COVARIANT_WALK=OFF -DCA_J0_TAU_RHO_WIDTH=2
cmake -S . -B /tmp/j0-rho-oriented -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_WERROR=ON -DCA_J0_RHO_COVARIANT_WALK=ON -DCA_J0_TAU_RHO_WIDTH=2
cmake --build /tmp/j0-rho-reference --target cryptanalysis_static
cmake --build /tmp/j0-rho-oriented --target cryptanalysis_static test_curve
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c /tmp/j0-rho-reference/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-reference-bench
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c /tmp/j0-rho-oriented/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-oriented-bench
python3 experiments/prime-j0-rho-coordinate-canon-20261002/panel.py --reference /tmp/j0-rho-reference-bench --candidate /tmp/j0-rho-oriented-bench --curve j0-36 --targets 64 --output /tmp/panel-j0-36.jsonl
python3 experiments/prime-j0-rho-coordinate-canon-20261002/panel.py --reference /tmp/j0-rho-reference-bench --candidate /tmp/j0-rho-oriented-bench --curve j0-37 --targets 64 --output /tmp/panel-j0-37.jsonl
python3 experiments/prime-j0-rho-coordinate-canon-20261002/panel.py --reference /tmp/j0-rho-reference-bench --candidate /tmp/j0-rho-oriented-bench --curve j0-46 --targets 32 --output /tmp/panel-j0-46.jsonl
```

`panel.py` records failed or timed-out attempts before stopping the panel.
The measured implementation's SHA-256 digests are `f289d7de36f53bbe06e7af02a4ffc19a72d6cd3584c5c4df2f2329a421a3b5d6`
for `src/curve.c`, `128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`
for `src/ec_tau.c`, and `e006f9b4a33d7dfc5a0e5e5ad3b0f336f2f03cfff3ad21b4acc6e9296876a025`
for the benchmark source. The panel script digest is
`4a4d54f1ad02c36e1a164673856fd7717fb0ac54392d13ec95b825b8c4fda82e`.

The fresh default Release build passed the full C suite, 15/15 tests.
`test_curve` passed 11,508 checks in Release and under UBSan, including
six-image representative checks on the registered j=0 curves and the
56-bit b=7 subgroup. The optional coordinate-only and width-4 variants
also passed their curve tests before the final test expansion.
