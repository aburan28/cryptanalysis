# Prime-field j0 tau arithmetic and rho setup

The correctness results and raw timings below are retained. CPU timing
ratios from these contended-host runs are exploratory until a qualifying
[isolated replay](../../docs/ISOLATED_BENCHMARKS.md) verifies them.

Source: the user-provided text of Guangwu Xu, Wei Yu, Ke Han, and Pengfei
Lu, *On Efficient Computations of y² = x³ + b/Fp for Primes p ≡ 1 (mod 3)*.
The supplied text has SHA-256
`8d20aca6b52c9b6d541e858bc97fe050528f4169c7283c8e2988042b2813d28e`.
Proposition 3.1 provides the Jacobian `tau = 1 - omega` and tripling formulas.

## Integration

`src/ec_tau.c` implements exact integer-lattice reduction of a 64-bit scalar,
a width-2 tau-NAF with digit orbit `{±1, ±omega, ±omega²}`, and the paper's
width-4 table built from nine seed coefficients and their sixfold unit orbit.
Both paths use Jacobian tau arithmetic and one affine conversion at the end.
`ca_ec_mul_tau4_tripling` also rewrites pairs of tau powers as powers of 3,
using the paper's Jacobian tripling formula.  Odd digits use a general
projective addition rather than the paper's augmented-tau precomputation,
so its field-operation count differs from Algorithm 3.  The scalar APIs
expect a point in the configured j0 subgroup.  `ca_ec_triple_j0` works for
any point on a supported j0 curve.

The width-4 rho build additionally prepares the nine seed points and their
nine tau images once for each of its fixed base and target points.  It batch
normalizes each 18-point table with one inversion, caches the scalar-reduction
lattice and digit table, and uses native 64-bit digit recoding when reduced
coordinates fit a guarded range.  The original signed-128 recoder remains
the fallback.  Preparation is charged inside each rho online interval.

Rho uses width 2 by default for jump-table points and restarts.  Set
`CA_J0_TAU_RHO_WIDTH=4` for the tripling variant, or
`CA_J0_TAU_RHO=OFF` for the affine reference.  Its sixfold automorphism
folding and batched affine walk remain the same.

The paper's reported 256/384/512-bit field-multiplication costs and regular
side-channel variant are separate from these measurements.  This
implementation uses variable-time branches and inversions.

## Paired one-target rho check

The online interval is `ca_curve_solve` entry through recovered and internally
verified scalar.  It includes the target-dependent jump table, restarts,
walk, collision, and recovery check.  Curve setup, generator selection,
fixture construction from the known scalar, process launch, and the
independent replay in `bench_rho.c` are outside that interval.  Both builds
use the same public target point, seed `20260930`, one CPU thread, and the
solver's identical walk/DP policy.  Twelve repetitions measure timing
variation for that one target; they are not twelve independent DLP targets.

| Curve | Public target `(x,y)` | Affine median ms | Tau median ms | Affine / tau | Verified |
| --- | --- | ---: | ---: | ---: | --- |
| `glv-j0-26` | `(66359801,41868878)` | 1.9040 | 1.4235 | 1.34 | 12/12 each |
| `glv-j0-32` | `(3450338692,2640858903)` | 0.4985 | 0.4285 | 1.16 | 12/12 each |

The [raw runs](rho_j0_26_off.txt),
[tau runs](rho_j0_26_on.txt),
[second curve affine runs](rho_j0_32_off.txt), and
[second curve tau runs](rho_j0_32_on.txt) retain each run's time, target,
seed, transformation count, and correctness.  The timings are short and
variable on this shared host; the ranges are 1.430–10.460 vs 1.376–2.854 ms
on `j0-26`, and 0.461–1.411 vs 0.405–1.401 ms on `j0-32`.  The operation
counter uses an affine add/double as one operation in the reference build,
and a Jacobian tau or mixed addition as one transformation in the new setup.
Its `S` value is therefore not comparable across these builds.  Online wall
time is the paired metric.

The [scalar control](scalar_results.txt) evaluates 20,000 frozen scalars per
round with both paths, checks identical point hashes, and records raw timings.
It shows significant system-load variation; these measurements do not
establish a universal scalar-multiplication speedup or a 256-bit result.

## Width-4 continuation

The [four-way scalar control](scalar_results_width4.txt) compares affine,
width 2, width 4, and width 4 with tripling on the same 20,000 scalars per
round.  Every path produced the same point checksum.  It includes the
56-bit prime subgroup of `y²=x³+7` over `F_(2^61-1)`, whose curve order is
`43 × 53624256071278747`.  Median per-round times in milliseconds were:

| Subgroup | Affine | Width 2 | Width 4 | Width 4 tripling |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-26` | 47.133 | 17.625 | 22.946 | 22.003 |
| `glv-j0-32` | 53.890 | 17.923 | 22.854 | 22.334 |
| `j0-56` | 235.659 | 39.601 | 41.624 | 39.938 |

These are scalar-stage diagnostics, including per-call preparation, rather
than single-target DLP timings.  The complete rho
check below uses the same one target and seed as the earlier comparison;
width 2 and width 4 are run in alternating order for twelve timing pairs.
All answers passed internal recovery verification and independent scalar
replay.  Setup for the selected scalar path is inside each online interval.

| Curve | Width-2 median ms | Width-4 tripling median ms | Width-4 / width-2 | Verified |
| --- | ---: | ---: | ---: | --- |
| `glv-j0-26` | 1.3800 | 1.3970 | 1.012 | 12/12 each |
| `glv-j0-32` | 0.4340 | 0.4380 | 1.009 | 12/12 each |

The [j0-26 width-2](rho_glv-j0-26_width2.txt),
[j0-26 width-4](rho_glv-j0-26_width4.txt),
[j0-32 width-2](rho_glv-j0-32_width2.txt), and
[j0-32 width-4](rho_glv-j0-32_width4.txt) files contain all online times,
transformation counts, and correctness results.  Width 2 is retained as
the default on these workloads.  The width-4 source at this measurement
had SHA-256 `abcdad7a2bef0d74e1e8318e06dfd6c560cd1bd98f766aee3caf7d768079abd2`
for `src/ec_tau.c` and
`8251b95840e0d2051228af92df3ad997dce4ca0faea940cdaae1978ee62ae3d0`
for `src/curve.c`.

## Prepared width-4 iteration

The prepared implementation was compared with the unchanged width-2 rho
default on the same two public target points and seed shown above.  Builds
used the same Release flags and one CPU thread.  The script
[`bench_prepared_pair.py`](bench_prepared_pair.py) alternates execution order
within each pair; each row is one complete solve of the same target, with
internal recovery verification and independent scalar replay.  Timings include
both base and target table preparation, all jump and restart scalars, the
walk, and recovery verification.  These repetitions measure timing noise,
not a distribution of different DLP targets.

The final 24-pair run after guarded 64-bit recoding gave:

| Curve | Width-2 median ms | Prepared width-4 median ms | Median paired width-2 / width-4 | 95% bootstrap interval | Width-4 faster pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-26` | 1.3905 | 1.3835 | 1.0014 | 0.9844–1.0235 | 13/24 |
| `glv-j0-32` | 0.4290 | 0.4180 | 1.0358 | 1.0048–1.0526 | 18/24 |

All 96 solves in this run verified.  The bootstrap resamples paired timing
ratios with seed `20261001`; its interval describes repeated timing on this
same point and machine.  The [final j0-26 rows](prepared-fast-recode-repeat/rho_glv-j0-26_width4_prepared_pair.txt)
and [final j0-32 rows](prepared-fast-recode-repeat/rho_glv-j0-32_width4_prepared_pair.txt)
have their paired width-2 files beside them.  A preceding 48-pair run under
high host load is retained in [`prepared-fast-recode/`](prepared-fast-recode/):
the median paired ratios were 1.0004 and 1.0273, respectively.  That run
showed wide timing variation on `j0-26`; the final run was made after load
eased.  Earlier 12-pair table-preparation and 24-pair cached-lattice runs are
also retained in the experiment directory.

This is a small verified one-target online improvement for `j0-32` on this
ARM64 host.  It does not establish a gain on `j0-26`, across target points,
or on 256-bit curves.  Width 2 therefore remains the default, and width 4
stays an explicit build choice.  Transformation counts differ in the setup:
the final run recorded 13,513 versus 13,209 on `j0-26`, and 4,221 versus
3,981 on `j0-32`, for width 2 versus prepared width 4.  These are unlike
primitive transformations and are not a speedup metric.

A [larger-subgroup continuation](large-rho-20261002/README.md) completed
paired one-target rho solves on 36-, 38-, and 46-bit prime subgroups over a
61-bit field.  It found a 1–3% prepared width-4 gain on four frozen targets
and a tie on two; all 288 solves verified.  This remains a small, target-
dependent result, so width 2 stays the default.

A separate [oriented sixfold rho-walk experiment](../prime-j0-rho-coordinate-canon-20261002/README.md)
uses the same width-2 tau setup in both builds and changes the walk itself.
Its expanded frozen one-target panels measured median paired online wall
ratios of 2.785×, 3.375×, and 3.260× on the 36-, 38-, and 46-bit subgroups,
with all 320 solves verified. The oriented walk is now the default j=0
walk; this tau window comparison remains a distinct setup question.

The final measured sources have SHA-256
`128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`
for `src/ec_tau.c`,
`5bc8ba85ed47fe8c51d38b00f8ed81a97616eb3d246957fc6f7cabac6c65ff3b`
for `src/ec_tau_internal.h`, and
`241baa402d0dbb4432f0157cc63867ed83436586ac267ed94942d3f0d4560c69`
for `src/curve.c`.

Environment: Darwin 25.6.0 arm64; Apple clang 17.0.0; Release build,
`CA_CUPQC=OFF`, default portable CPU code.  The `CA_J0_TAU_RHO` flag is the
only algorithm change between the paired builds.  Source hashes at the rho
measurement were `src/ec_tau.c`
`a73b8d1169045b646db591f7037e11cdf99b23a2b9c5daa37baa9fff065d2293`
and `src/curve.c`
`bccd24b7cd364b194741d47a6447fe951637cf2c33f52ad57b32a328ba31913b`.

## Reproduce

```sh
cmake -S . -B /tmp/j0-on -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_J0_TAU_RHO=ON
cmake -S . -B /tmp/j0-off -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_J0_TAU_RHO=OFF
cmake -S . -B /tmp/j0-w4 -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_J0_TAU_RHO_WIDTH=4
cmake --build /tmp/j0-on --target cryptanalysis_static test_curve
cmake --build /tmp/j0-off --target cryptanalysis_static
cmake --build /tmp/j0-w4 --target cryptanalysis_static test_curve
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/bench_rho.c /tmp/j0-on/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-on
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/bench_rho.c /tmp/j0-off/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-off
/tmp/j0-rho-off glv-j0-32
/tmp/j0-rho-on glv-j0-32
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/bench_rho.c /tmp/j0-w4/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-w4
python3 experiments/prime-j0-tau-20260930/bench_prepared_pair.py --width2 /tmp/j0-rho-on --width4 /tmp/j0-rho-w4 --output /tmp/j0-prepared-pairs --pairs 24
python3 experiments/prime-j0-tau-20260930/summarize_prepared_pair.py /tmp/j0-prepared-pairs
```

The full Release C suite passed, 15/15 tests.  `test_curve` additionally
checks 256 scalars on each registered j0 curve, all scalars on three small
prime-order curves, 128 scalars on the 56-bit subgroup, aliasing, identity,
and the tripling exceptions at 3-torsion and 2-torsion.  The final curve test
passed 6,631 checks in Release and under UBSan.  These are correctness
checks on this ARM64 host;
no x86-64 or accelerator performance claim is made.
The prepared width-4 continuation passed the full Release suite, 15/15,
and `test_curve` passed 8,772 checks in both Release and a width-4 UBSan build.
