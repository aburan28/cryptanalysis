# Round 60: input buffers validated, complete-query timing unqualified

The leased-buffer path passes all 92 frozen optimized/UBSan preflight records:
20 verified complete PDP queries, 20 independently certified algebra controls,
and 52 retained native work-budget failures. Both arms use the same indexed F4
binary and unchanged independent checker. Bases, derivation proofs, integer
producer/checker traces and column statistics match the frozen round 58 inputs.
The portable audit independently replays seven distinct proofs and the solved
curve controls, and verifies 149 source, generated-file, resource and binary
bindings.

All 15 test groups pass. Input-specific checks cover 64 random ideals, bitsets
with up to 4096 equations, every work budget from 0 through 512, proof/row limits,
zero compaction, shrinking/growing active support, fresh target alternation,
invalid partial fills, and stable array addresses. Stale, nested, wrong-ring,
wrong-query and foreign-thread leases are rejected. Four-thread reuse of one
workspace produces the same fresh results as the legacy path. The eight paired
measurement rejection tests also pass.

The first validation attempt stopped before solver tests because the new query
module lacked a declaration imported by the existing extraction helper. That
import compatibility issue was corrected; its log and source receipt remain
retained. The final build, tests, preflight, measurement recording and independent
audit pass.

The local timing attempt admits zero queries: one-minute host load is 210.6421
against a threshold of 14 logical CPUs. Two rejected admissions and 31 unrun
trials remain recorded. Acceptance and the 2x target are false; speed ratios are
unknown. Preflight timing fields are diagnostics, not eligible latency results.

Local validation ran on physical Apple M4 Pro ARM64, 14 logical CPUs and 48 GiB
RAM, macOS 26.6, Python 3.13.1. Native libraries were rebuilt locally. Hosted
Linux x86-64 and macOS ARM64 rebuilds and complete-query panels are configured
in CI and remain pending until their artifacts have been independently checked.

The implementation removes the final descent dictionary and per-query native
input-array allocation on the buffered path. It still computes every target's
coefficients, solving and certification afresh. The benchmark charges buffer
filling, lease acquisition, native decoding, independent verification, original
equation/curve checks, and lease teardown. Whether this saves complete-query
time remains an empirical question; the path stays opt-in.
