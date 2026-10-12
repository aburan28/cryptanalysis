# Bounded radix sorting of monomial-order keys

This frozen experiment changes only the sorting implementation within
`ordered_multiple`. It has four arms: the unchanged producer (`baseline`),
round98's always-key comparison sorter (`keys`), radix with a 32,768-word
scratch cap (`radix`), and radix with a 256-word cap (`tiny`). Both radix arms
use a fixed 128-term cutoff, chosen before timing. One word is eight bytes.
No arm incorporates round97 normal-merge scratch reuse.

Radix uses the proved round98 57-bit monomial representation. Stable counting
passes process bytes from least to most significant. A byte identical in every
key can be skipped without changing order. Stability preserves the order from
all lower processed bytes, so the final key sequence equals unsigned comparison
sorting. Every word is decoded before cancellation, proof emission or output.
Small rows and rows exceeding the cap fall back to packed-key comparison sorting;
rows with any mask bit above 56 retain the original monomial comparator.

Scratch belongs to one Engine instance and is destroyed at query completion.
Its actual capacity is checked against the cap; an oversized allocation is
released and comparison sorting is used. The cap applies to retained radix
scratch, not output rows, all process memory or the transient capacity before
release. A 256-bin count/offset array is local to one pass. No numeric rows or
answers are retained between queries. Input work charges happen before sorting,
and node emission occurs after decoding, preserving work/proof stopping rules.

For fixed 64-bit words there are at most eight counting passes. This replaces
one comparison-sort step with bounded linear passes; it does not prove a new
asymptotic Gröbner-basis algorithm or an F6 result. Encoding, byte checks,
histograms, scattering, copyback, allocations and fallback are all included in
complete-query timing.

Freeze sources and this panel before one diagnostic run. Require optimized and
UBSan correctness, exact multiplication against the unchanged source, stable
sorting with duplicates/cancellation, zero/odd/even pass counts, cutoff/cap
boundaries, high-bit fallback, changing-target queries and concurrency. Audit
mathematics without loading downloaded native code. Preserve failures and all
observations; no selected reruns.

The CPU-only component diagnostic keeps the same 23 algebra/planted-PDP inputs,
four paired arms, two warmup rounds and four observation rounds. Reusable setup
is separate; fresh coefficient descent, solving, independent certification,
extraction/replay and teardown are charged. The local host lacks an isolation
receipt, so qualified/aggregate/online speedups remain null. Keep default CPU
dispatch unchanged. These controls do not establish ordinary relation yield,
complete IC/rho performance, a GPU crossover or globally fastest F4/F5.
