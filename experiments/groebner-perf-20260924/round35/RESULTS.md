# Fixed-block symmetry: measured results

Two independent wide trials and two complete small trials passed the predeclared load gate on a physical Apple M4 Pro (14 logical CPUs, 48 GiB). All 7,200 queries in these four trials returned independently verified complete answers. The offline source-bound audit also checked original equations, full proof identities, complete roots, bases, work counts, memory accounting, curve witnesses, and journals. These are frozen planted PDP component controls, not full IC/rho measurements.

## Direct complete-query comparisons

The confirmation wide trial used seven measured pairs plus one warmup for each frozen input. All times below are median complete-query wall times in milliseconds. Ratios are paired geometric means with 95% paired-bootstrap intervals; they are not ratios multiplied across experiments.

| Boolean variables / seed | Older exact CPU (round33) | Previous affine CPU (round34) | Symmetry CPU (round35) | Previous / symmetry | Older / symmetry |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21 / 201 | 12.363 | 12.368 | 8.036 | 1.535× [1.521, 1.548] | 1.531× [1.515, 1.547] |
| 21 / 202 | 12.508 | 12.557 | 8.223 | 1.540× [1.530, 1.546] | 1.521× [1.516, 1.527] |
| 21 / 203 | 12.396 | 12.581 | 8.125 | 1.534× [1.516, 1.551] | 1.510× [1.491, 1.529] |
| 24 / 201 | 84.179 | 81.002 | 47.633 | 1.707× [1.698, 1.716] | 1.764× [1.746, 1.781] |
| 24 / 202 | 83.950 | 81.454 | 48.054 | 1.689× [1.671, 1.704] | 1.805× [1.736, 1.931] |
| 24 / 203 | 84.652 | 81.685 | 47.723 | 1.759× [1.695, 1.877] | 1.764× [1.739, 1.789] |
| 27 / 201 | 2936.250 | 1471.226 | 816.096 | 1.815× [1.798, 1.833] | 3.611× [3.591, 3.634] |
| 27 / 202 | 2941.761 | 1472.403 | 817.820 | 1.796× [1.777, 1.811] | 3.584× [3.548, 3.612] |
| 27 / 203 | 2987.537 | 1499.041 | 835.220 | 1.790× [1.758, 1.814] | 3.948× [3.540, 4.743] |

The seed203 interval is wider because one retained baseline observation took 5,682 ms. Its median baseline/candidate ratio is about 3.58×, while its paired geometric mean is 3.95×. The outlier is retained; this is not a claim of a reliable 4× improvement.

The round33 comparison uses unchanged native source with producer and checker enumeration bounds expanded to 2^27 so that it finishes these same inputs. Round34 and round35 retain identical normal limits. This is an explicit paired baseline, not a global strongest-solver claim.

## Repetition and small/device controls

| Trial | Queries including warmups | Maximum one-minute load | Timing eligible |
| --- | ---: | ---: | --- |
| wide-1.json.gz | 432 | 13.051758 / 14 | Yes |
| wide-2.json.gz | 432 | 13.391602 / 14 | Yes |
| small-2.json.gz | 3168 | 8.531738 / 14 | Yes |
| small-3.json.gz | 3168 | 13.919434 / 14 | Yes |

A separate small-1 attempt stopped at an ENOSPC journal write. Its original journal was compressed with a byte-for-byte SHA-256 round-trip check, retaining 6,810 valid checkpoints and 3,121 query results. It is an interrupted attempt and is excluded from every performance win. Replacement trials kept the same source, inputs, repetitions, limits and query boundary; active journals moved to the system volume outside the timed interval.

wide-1.json.gz: all 9/9 wide controls have a qualified round34-to-round35 CPU win.
wide-2.json.gz: all 9/9 wide controls have a qualified round34-to-round35 CPU win.

Small controls compare six CPU implementations and five requested Metal implementations. The table shows the new CPU ratio against the immediately preceding affine CPU and the new Metal ratio against the fastest CPU in each measured pair.

| Trial / input | Previous CPU / symmetry CPU | Best paired CPU / symmetry Metal | GPU win |
| --- | ---: | ---: | --- |
| small-2 / n31-m3-ell6-seed101 | 1.359× [1.338, 1.378] | 1.503× [1.457, 1.540] | Yes |
| small-2 / n31-m3-ell6-seed102 | 1.329× [1.308, 1.350] | 1.491× [1.463, 1.521] | Yes |
| small-2 / n31-m3-ell6-seed103 | 1.360× [1.323, 1.412] | 1.472× [1.449, 1.494] | Yes |
| small-2 / n31-m3-ell6-seed104 | 1.331× [1.315, 1.348] | 1.485× [1.450, 1.517] | Yes |
| small-2 / n31-m3-ell6-seed105 | 1.340× [1.322, 1.359] | 1.471× [1.438, 1.502] | Yes |
| small-2 / n31-m3-ell6-seed106 | 1.341× [1.314, 1.363] | 1.462× [1.427, 1.495] | Yes |
| small-2 / n31-m3-ell5-seed101 | 1.106× [1.069, 1.144] | 0.960× [0.938, 0.981] | No |
| small-2 / n11-m3-ell3-seed101 | 1.049× [0.966, 1.145] | 0.436× [0.412, 0.461] | No |
| small-2 / n83-m3-ell2-seed101 | 1.016× [0.993, 1.057] | 0.971× [0.948, 0.985] | No |
| small-3 / n31-m3-ell6-seed101 | 1.335× [1.323, 1.346] | 1.075× [1.035, 1.114] | Yes |
| small-3 / n31-m3-ell6-seed102 | 1.339× [1.327, 1.350] | 1.072× [1.013, 1.123] | Yes |
| small-3 / n31-m3-ell6-seed103 | 1.334× [1.320, 1.349] | 1.099× [1.071, 1.129] | Yes |
| small-3 / n31-m3-ell6-seed104 | 1.338× [1.325, 1.351] | 1.075× [1.045, 1.108] | Yes |
| small-3 / n31-m3-ell6-seed105 | 1.310× [1.249, 1.350] | 1.050× [1.010, 1.090] | Yes |
| small-3 / n31-m3-ell6-seed106 | 1.337× [1.324, 1.351] | 1.061× [1.019, 1.103] | Yes |
| small-3 / n31-m3-ell5-seed101 | 1.107× [1.085, 1.128] | 0.644× [0.603, 0.690] | No |
| small-3 / n11-m3-ell3-seed101 | 1.051× [0.981, 1.137] | 0.423× [0.408, 0.439] | No |
| small-3 / n83-m3-ell2-seed101 | 1.031× [0.917, 1.162] | 0.815× [0.701, 0.927] | No |

Metal remains opt-in. The unchanged kernel still eliminates every branch on supported shapes; the host consumes representatives. Requested Metal at 24/27 variables explicitly falls back to CPU and cannot qualify as a GPU win. Neither CUDA compatibility nor a GPU speedup on the wide frontier is established.

## Mechanism and remaining cost

On the confirmation 27-variable seed203 control, the producer solves 131,328 representatives instead of 262,144 branches. It copies 79,782 constant proofs and 51,031 affine proofs and expands three alias roots. Direct affine generation performs 3,089,715 row insertions and 24,855,775 pivot-row XORs. The full wire proof is unchanged from round34 on all measured fixtures. The checker still checks 102,241 affine identities and enumerates 3,072 original residual assignments. No target answers are reused.

The same control has about 535 ms in affine certificate generation and 106 ms in independent verification. Fresh specialization takes about 20 ms; the symmetry check about 3 ms and expansion about 7 ms. These are nested diagnostics, not additive exclusive phases. The full median query is about 835 ms. The offset maps add 2,097,156 bytes; reported workspace sizes are accounted allocations, not process peak RSS.

## Validation and follow-up

Local validation passed 35 test groups covering exhaustive three-variable Boolean functions, coefficient widths through 128 equations, duplicate cancellation, fresh symmetric/asymmetric reuse, CPU/Metal equivalence, UBSan, complete queries through 27 variables, unchanged independent verification, budget/root-limit failures, forged proof records, and audit mutations. The separate deferred-proof pilot passed 4,096 exhaustive small matrices and 300 random matrices; it has no native speed claim. CI rebuilds the code on Linux and macOS and audits both fresh and retained correctness reports.

See [the implementation and reproduction contract](README.md), [the next experiments](NEXT.md), and [machine-readable audited timing summaries](results/performance-audits.json). The retained compressed correctness reports include full source/build snapshots and raw proof journals. Full timing journals and the interrupted trial are archived separately in the task evidence directory.

`candidate_id`, `IC_online_ms`, and `rho_online_ms` remain null. These results do not prove a novel asymptotically faster F6 algorithm, natural relation yield, a globally fastest F4/F5 implementation, or full single-target IC acceleration.
