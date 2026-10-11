# Larger prime-field j=0 one-target rho controls

This continuation tests the Xu–Yu–Han–Lu tau setup on complete one-target
rho solves beyond the two small registered curves.  The checked repository
`./sage` launcher ran the [curve factorization probe](probe_curves.py)
after [runtime verification](sage-runtime-info.json).  Its exact fixtures are:

| Workload curve | Field and model | Full curve order | Prime subgroup order | Cofactor |
| --- | --- | ---: | ---: | ---: |
| `j0-37` | `F_(2^61-1)`, `y²=x³+11` | 2305843006203085756 | 157632877033 | 14627932 |
| `j0-36` | `F_(2^61-1)`, `y²=x³+5` | 2305843008054377925 | 51131959441 | 45095925 |
| `j0-46` | `F_(2^61-1)`, `y²=x³+13` | 2305843012224302148 | 42111239174233 | 54756 |

The probe factored the orders as `2²·11²·30223·157632877033`,
`3·5²·7³·1753·51131959441`, and `2²·3⁴·13²·42111239174233`,
respectively.  The field has 61 bits; the DLP subgroup orders appear in the
table separately.  `ca_curve_group` independently sets the cofactor and
finds a generator; each [benchmark row](target_a/rho_j0-37_width2_prepared_pair.txt)
records its encoded base, target, subgroup order, recovered scalar, walk seed,
distinguished-point entries, reported table memory, online time, and result.

## Frozen one-target comparisons

Each workload fixes one public target and rho seed `20261002`.  The target is
generated from the listed fixture scalar before timing, and each width-2 or
prepared width-4 invocation solves that same target from an empty table.
The timer is inside `ca_curve_solve`: it includes the target-dependent jump
table and restarts, width-4 point preparation, walk, collision recovery, and
internal scalar replay.  It excludes process launch, curve setup, generator
selection, target construction, and the second independent scalar replay in
[`bench_rho_large.c`](bench_rho_large.c).  Both builds use one CPU thread,
identical folded-walk/DP policy and seed, and alternating execution order.
Twenty-four pairs per target estimate timing variation on that target; they
are not 24 independent DLP targets.

| Curve and target | Fixture scalar | Width-2 median ms | Width-4 median ms | Median paired width-2 / width-4 | 95% paired bootstrap interval | Width-4 faster pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `j0-37` [A](target_a/) | 98065508441 | 23.3450 | 23.1170 | 1.0116 | 1.0055–1.0156 | 20/24 |
| `j0-37` [B](target_b/) | 4886718345 | 12.7265 | 12.4515 | 1.0212 | 1.0167–1.0326 | 20/24 |
| `j0-37` [C](target_c/) | 8152752965 | 32.0650 | 31.9070 | 0.9985 | 0.9886–1.0022 | 9/24 |
| `j0-36` [A](j0-36-target-a/) | 11885659636 | 10.4440 | 10.3005 | 1.0116 | 1.0089–1.0178 | 21/24 |
| `j0-46` [A](j0-46-target-a/) | 6403380589761 | 119.8825 | 116.7820 | 1.0276 | 1.0207–1.0316 | 23/24 |
| `j0-46` [B](j0-46-target-b/) | 4886718345 | 414.0360 | 411.7655 | 0.9985 | 0.9865–1.0113 | 11/24 |

All 288 solves verified, with an independent replay outside the online
timer.  The paired bootstrap resamples timing ratios 10,000 times with seed
`20261001`, as implemented in
[`summarize_prepared_pair.py`](../summarize_prepared_pair.py).  It measures
timing variation for each fixed point on this ARM64 host.  The `j0-37` target
C and `j0-46` target B show no supported gain.  The measured gains apply to
the listed targets and hardware.  The 48-pair preliminary run on target A is preserved in
[`paired-j0-37/`](paired-j0-37/) and gave a median paired ratio of 1.0117.

The reported distinguished-point table held 7,251, 3,944, 9,917, 3,643,
35,218, and 126,576 entries respectively for the six workloads.  The solver
reported a 394,240-byte table peak for the 36- and 38-bit workloads and
6,292,480 bytes for the 46-bit workloads.  The same target and seed yielded
the same entries in both builds.  The `ops` fields count unlike setup transformations between
widths, so online wall time is the comparison metric.  These measurements
support retaining width 4 as opt-in while width 2 remains the default.

## Reproduce

```sh
./sage --runtime-info > experiments/prime-j0-tau-20260930/large-rho-20261002/sage-runtime-info.json
./sage -python experiments/prime-j0-tau-20260930/large-rho-20261002/probe_curves.py
cmake -S . -B /tmp/j0-large-w2 -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_BUILD_SHARED=OFF -DCA_BUILD_TOOLS=OFF -DCA_BUILD_TESTS=OFF -DCA_J0_TAU_RHO_WIDTH=2
cmake -S . -B /tmp/j0-large-w4 -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_BUILD_SHARED=OFF -DCA_BUILD_TOOLS=OFF -DCA_BUILD_TESTS=OFF -DCA_J0_TAU_RHO_WIDTH=4
cmake --build /tmp/j0-large-w2 --target cryptanalysis_static
cmake --build /tmp/j0-large-w4 --target cryptanalysis_static
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c /tmp/j0-large-w2/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-large-w2
cc -O3 -std=c11 -Iinclude experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c /tmp/j0-large-w4/libcryptanalysis.a -lm -lpthread -o /tmp/j0-rho-large-w4
python3 experiments/prime-j0-tau-20260930/bench_prepared_pair.py --width2 /tmp/j0-rho-large-w2 --width4 /tmp/j0-rho-large-w4 --output /tmp/j0-37-target-a --curves j0-37 --pairs 24 --scalar 0x5d2e739b4c1 --walk-seed 20261002
python3 experiments/prime-j0-tau-20260930/summarize_prepared_pair.py /tmp/j0-37-target-a --curves j0-37
```

The source hashes for the measured builds are `128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`
for `src/ec_tau.c`, `5bc8ba85ed47fe8c51d38b00f8ed81a97616eb3d246957fc6f7cabac6c65ff3b`
for `src/ec_tau_internal.h`, `241baa402d0dbb4432f0157cc63867ed83436586ac267ed94942d3f0d4560c69`
for `src/curve.c`.  The 36- and 38-bit rows used
`bench_rho_large.c` hash `7eb588d81dff975fd0d91cfc187e429fdc7759ab69d05cf0c8d5e544bb66022e`;
the 46-bit rows used hash
`01d16a76b78bb4099af4144053449dd7273ea230d3af76c84e4117e0112de1db`
after adding the `j0-46` fixture.  Host: Darwin 25.6.0 arm64, Apple clang 17.0.0,
Release portable CPU build.  The earlier 15/15 Release suite and 8,772-check
width-4 UBSan curve test cover the unchanged core implementation; this
continuation adds verified end-to-end solves on the larger subgroups.
