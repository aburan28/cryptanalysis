# Two-coordinate affine rotation table

The radix-14 affine-layer scalar batch stores each selected point as
`(x, m, y)`, with `m = x + βx` and `β² + β + 1 = 0`. A rotation by `β` uses
`m - x`; a rotation by `β²` uses `-m`. This replaces the corresponding
constant field multiplications during leaf selection with field additions.
The candidate retains 37,192,948 table bytes versus 26,035,988 for the
affine-layer reference. Table preparation remains outside the 128-output,
96-pass online interval and is recorded separately.

For the identity, multiply `β² + β + 1 = 0` by `x` to obtain
`x + βx + β²x = 0`. Hence `m = -β²x`, so `-m = β²x`; subtraction directly
gives `m - x = βx`. [TwoX.lean](TwoX.lean) proves both implications over an
abstract additive group whose laws and orbit identity are explicit
hypotheses. The declaration `TwoX.recover_rotated_x` was checked with pinned
Lean 4.34.1 using `lean TwoX.lean`; `#print axioms` reported none. The
checked output is in [lean-check.log](lean-check.log). The curve-specific
fact that the native `β` satisfies its cubic identity is supplied by the
existing split-prime implementation and its independent point replay, not
encoded as an axiom in this theorem.

The hash-guarded overlay [native_two_x_overlay.py](native_two_x_overlay.py)
produced front source SHA-256
`abb8d153fe3d2956536a86f3d049cf4f783fd24ee6f7753d624b45cd6d96b416`
and window source SHA-256
`50246c1c5174f4f38d37346118c92a1157fb2f72d98d10cec65ea549d52032ad`.
The Linux release binary SHA-256 is
`23fb61a8ed804b3bd7925a730b9aff429eebdc3502950baacaf4ecfd04c00996`.
The native release test covered 128 frozen independent scalar outputs, the
identity, and independent binary scalar replay. The first compile attempt
failed on a table-type mismatch; the retained `linux-test-attempt1.log`
records it. The corrected test and release build passed.

An exploratory sequential A/B/A sizing screen on the pod gave reference
57.042500 ms, candidate 54.514767 ms, reference 56.539497 ms. All three
reported `verified=1`, the same fixture SHA, 12,288 output count, and the
same result point. This screen is a lead only.

The frozen Tier 1 panel is specified by
[tier1-two-x-cpu40-manifest.json](tier1-two-x-cpu40-manifest.json) and
[tier1-two-x-cpu40-rules.json](tier1-two-x-cpu40-rules.json). It alternates
reference and candidate order on CPU 40 for 16 repetitions per case, with
adjacent A/A calibrations. Job `0131d510f20941bc81104accf08cf0fa` runs
through the pod's single-job queue. The runner records exposed affinity,
cgroup, CPU throttling, frequency, interrupts, steal time, and memory
placement. Host exclusivity and physical CPU isolation are unverified, so
the panel is Tier 1. Retain every raw pair, including any failed noise gate.

The job completed with 96 valid arms, 48 valid pairs, and unchanged artifact
hashes. [analyze_tier1.py](analyze_tier1.py) independently checked the full
manifest, expected point and fixture for every arm, source and binary hashes,
and all adjacent A/A pairs. No A/A ratio fell outside `[0.90, 1.11]`. The
comparison-only median reference/candidate ratio is **1.037997**, with a
paired bootstrap 95% interval of **[1.025659, 1.053525]** over 16 comparison
repetitions. Mean online times per 12,288 outputs are 56.458543 ms for the
affine-layer reference and 54.416974 ms for the two-x table (4.594608 and
4.428465 µs/output respectively). Preparation means are 4196.115 and
4230.430 ms. This is a qualified Tier 1 batch-throughput comparison under
the frozen panel rules, not a single-scalar latency measurement.

The generic runner's `paired_speedup=1.006040` is the median of the three
case medians, including two A/A cases. Its `speedup_claim_eligible=false`
reflects that a three-case calibration panel has no generic cross-case
bootstrap interval. The predeclared case-specific audit uses A/A only as
noise gates and computes the comparison interval separately. The audit JSON
is [tier1-two-x-cpu40-audit.json](tier1-two-x-cpu40-audit.json). The raw
receipt directory is
[0131d510f20941bc81104accf08cf0fa](0131d510f20941bc81104accf08cf0fa),
copied from the pod in an archive whose SHA-256 was
`5875cab3a69e2dd0e0fe01d19b700d77a4aa6ffbb58ab4e535cfb3f2ad5bc0f4`
at both ends. The separate native provenance archive contains the exact
Linux build, test, failed first compile, sizing screen, and source files;
its SHA-256 is
`3f4473284c867dda7a8d7963e8b2588dfe25747c5c0507c2ed2fb009651649e5`.
