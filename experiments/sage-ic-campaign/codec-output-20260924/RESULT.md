# Native Sage point-output codec: local result

The candidate changes only the NTL decoder's construction of standard
finite-field point objects. The paired comparison uses the same installed
hardware plans with the preceding codec binary loaded separately as the
incumbent. Each full warm call charges packing, CPU or Metal execution,
ordinary Sage-point reconstruction, exact output verification and cleanup.
Plan setup is recorded separately. Twelve balanced rounds per cell use at
least 65,536 output points per arm and round.

| Phase | GF(2^m) | Points | Power | CPU gain | Metal gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary | 19 | 1,024 | 1 | 1.783× | 1.214× |
| Primary | 131 | 4,096 | 1 | 2.541× | 1.512× |
| Primary | 131 | 4,096 | 65 | 2.557× | 1.418× |
| Primary | 131 | 16,384 | 65 | 1.998× | 2.284× |
| Confirmation | 31 | 2,304 | 7 | 2.270× | 1.465× |
| Confirmation | 163 | 2,304 | 65 | 2.210× | 1.394× |

The primary geometric mean over eight CPU/Metal cells is **1.851×**; the
independent confirmation mean over four cells is **1.789×**. All
**18,997,248 timed outputs** matched the Sage Frobenius isogeny result.
Fresh-process peak RSS for a 4,096-point degree-131 CPU call changed from
276,512,768 to 276,758,528 bytes, an increase of 0.23 MiB (0.09%).
The frozen gate required both means above 1.05×, every cell at least 0.98×,
exact outputs, and RSS within 5% or 2 MiB. The second run passes those
declared local criteria.

The shorter first pilot had one 0.900× Metal cell and failed its gate. It
is retained in `run-001/`; no timings were pooled across attempts. The
longer `run-002/` used new seeds and the same candidate source and installed
binary, with its sampling change frozen in `intent-v2.json` before timing.
The host was shared, so these are local paired measurements rather than a
device-independent performance guarantee.

The codec-specific tests check standard point state, subsequent arithmetic,
copying, pickling, hashing, alternate NTL contexts, custom point subclasses,
and infinity. They passed two test groups. The installed CPU/Metal hardware
suite passed its six existing groups with the candidate codec. Both logs
are archived. No kernel or lookup-table change is part of this result.

This improves one warm plan API stage. It does not measure a complete
index-calculus pipeline or establish a discrete-logarithm speedup.
