# Staged fixed-base lookup: verified candidate and isolated panel

The staged U14 evaluator computes all fourteen signed-word digit choices
before point accumulation and issues two read-prefetch hints for each
selected 72-byte table entry while recoding continues. It then loads
the same entries, applies the same unit actions, and executes the same
mixed additions in the same order as the reference. The candidate
adds a fixed sixteen-choice stack array; it shares the existing scalar
selector, point table, and field arithmetic. The hypothesis is reduced
table-access latency, with no claimed arithmetic-operation saving.

The [source-bound receipt](verification.json) records a release binary
SHA-256 of
`20968f24e745e64c3184f33c9439ec8653cd784ba9b30749271dc05e9f98176b`.
The native release suite passed **67 tests**. Its new test compared the
candidate with the signed-word U14 reference on all **519** frozen
scalars, including scalar representative, nonidentity-add count,
retained table bytes, and final point; **128** fresh points also matched
an independent binary double-and-add evaluator. Both CLI fixture modes
verified all **129** independent expected points, and both benchmark
case entrypoints verified the same point. Each mode reported
**78,470,208 retained table bytes**. The staged path remains opt-in.

The protocol's original line about heap allocation was corrected after
the serial replay began: the shared lattice selector already allocates
a vector, while the staged choices add only a stack array. The verifier
also gained an end-of-run source-consistency check. An x86-only block
was marked `unsafe` after a cross-compile exposed the intrinsic's Rust
requirement; the ARM64 executable is byte-identical to the tested one.
The immutable [initial receipt](verification-initial.json) retains the
sources and raw outputs as they were at run start. The final receipt was
produced by [`amend_receipt.py`](amend_receipt.py), which reconstructed
these three exact edits, verified the original hashes, rechecked every
recorded source hash, the ARM64 binary hash, all command exits, and every
raw output hash. It records that the **67-test suite was reused**; no
second ARM64 test execution is implied. The raw suite reports **539.50
seconds** on the heavily contended local host; that duration is not a
scalar performance measurement.

The [isolated panel](ISOLATED_PANEL.md) pairs the signed-word reference
and staged candidate in one binary on nine frozen fixture indices with
five repetitions. Its manifest generator requires the amended receipt,
current source hashes, raw-output hashes, and binary hash before
producing a job. Its local structural check passed with manifest
SHA-256
`4c4be9025c9ea4244dd2753127be1ffb05abaa3bfa0a48e4e5e6ef621257f457`;
the example CPU and cgroup values are placeholders for a qualifying
host. The complete online timer charges scalar reduction,
recoding, hints, lookups, unit actions, additions, affine conversion,
and expected-point verification. A qualifying host-level isolation
receipt is the remaining empirical gate. The reachable RunPod CPU Pod
fails that preflight, so CPU speedup remains unmeasured.

The implementation uses stable x86-64 SSE prefetch hints and AArch64
`prfm` assembly, with a no-op fallback elsewhere. The local release
tests establish ARM64 correctness. A release-mode cross-compile check
with Rust 1.98 for `x86_64-unknown-linux-gnu` passed after the `unsafe`
fix; [raw compiler output](x86-cross-check.log) is retained. A Linux
x86-64 execution and independent point replay will establish that
backend's correctness before any device-specific performance result.
Hardware may ignore hints or evict useful cache lines, so the paired
isolated run decides whether staging helps.
