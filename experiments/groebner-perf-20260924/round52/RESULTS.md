# Round52 physical validation and first timing attempt

The opt-in independent partial-affine checker copies fresh coefficients into
contiguous local storage once per reached nonzero record. The round51 producer
and GPU shader are unchanged. This candidate has correctness evidence; it has
no qualified elapsed-time result and does not promote backend routing.

Measured on a physical Apple M4 Pro, macOS 26.6 ARM64, Python 3.13.1, with 14
logical CPUs. Optimized, UBSan, and a dedicated coefficient-comparison build
were rebuilt locally. Unchanged dependencies were copied on the same host and
all 459 executed dependency bindings were verified before full validation.

- All 18 unit groups passed, including fresh valid/invalid/valid inputs,
  31/32/33/64/65/128-equation word boundaries, all transform modes,
  budget exits, zero witnesses, configuration, and private factory isolation.
- Both local and strided modes passed 72,012 frozen control records and 216
  complete queries each: CPU optimized, CPU UBSan, and physical Metal, with
  partial records and GPU projection independently enabled and disabled.
- All 216 complete-query proof hashes, roots, bases, assignments, and existing
  integer counters match the prior round51 implementation exactly.
- The native audit checked 173,132,868 cached coefficient reads across 63
  distinct query proofs and both full and tile16 transforms. Every read
  matched the independently reconstructed source table.
- Independent Python replay from the original ANFs passed all 216 query
  records and 63 unique proofs, including complete roots and reduced bases.
- Compiled ARM64 code contains the intended lazy copy, contiguous stack reads,
  and separate strided mode. This is code-generation evidence, not a timing
  measurement.

For the physical 27-variable queries with partial records and GPU projection:

| Frozen input | Original source-table reads | New source-table reads | Added copy writes | Local reads | Cache object |
| --- | ---: | ---: | ---: | ---: | ---: |
| n31-m3-ell9-seed201 | 9,637,092 | 1,212,100 | 1,212,100 | 9,637,092 | 448 bytes |
| n31-m3-ell9-seed202 | 9,482,440 | 1,192,182 | 1,192,182 | 9,482,440 | 448 bytes |
| n31-m3-ell9-seed203 | 9,712,118 | 1,220,886 | 1,220,886 | 9,712,118 | 448 bytes |

These are source-level accesses. They do not measure cache misses or total
machine loads, and the copy adds work. The cache-object size is not a native
stack high-water measurement. Existing verification-work budget charges and
parity counts remain unchanged; copy work is bounded and separately counted.

The first frozen seven-arm whole-query campaign started at
2026-10-03T03:53:27Z. Both allowed admissions were rejected: the observed
one-minute load was 52.2285–56.0044 against a limit of 14. There were zero
executed queries, zero qualified trials, and 34 explicitly unrun remaining
trials. The acceptance criterion did not pass. Retain this failed admission
when a later quiet-host attempt is added; do not replace it or relax its gate.

The first build-log attempt failed before compilation because the filesystem
reported no space. A later retry completed without deleting evidence. The
first unit attempt exposed two absent unchanged replay libraries in the new
worktree; their hash-matched dependencies were restored before the passing
suite. Both attempts remain in the local evidence directory.

Local evidence lives in the session's `partial-affine-locality` directory:
`physical-local-v1.json.gz`, `physical-strided-v1.json.gz`,
`cache-audit-v1.json`, `independent-audit-v1.json`,
`local-strided-prior-comparison.json`, `compiled-locality-audit.json`,
and `performance-v1/`. CI retains corresponding rebuilt per-platform evidence.

These are bounded Boolean Gröbner/PDP stage diagnostics. They do not establish
general F4/F5 performance, natural relation yield, a novel asymptotic algorithm,
or a complete independently verified single-target IC/rho speedup.
