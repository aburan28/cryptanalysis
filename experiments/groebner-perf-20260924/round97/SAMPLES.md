# Fresh baseline stack diagnostics

After the single preset timing panel, three separate five-second native stack
samples were taken on the unchanged optimized baseline: PDP 6/9/12 seed 1.
The driver holds the same local heavy-work lock, constructs fixture/layout setup
before sampling, then repeatedly executes fresh complete queries. Every query's
non-timing result must equal its frozen control, including proofs and replay on
the solved fixture. The runs completed 999, 206 and 67 calls respectively.
These counts are profiling controls, not throughput or multi-target IC results.

The [sampling archive](samples.tar.gz) retains the exact driver, sampler commands,
raw stacks, trace checks, source/binary hashes, symbol table, image UUID and
selected disassembly. The [custody receipt](samples-archive.json) verifies its
bytes. Archived native libraries are not executed by that custody check.
This is the same Mac host without a qualifying isolation receipt. The sampler
and per-query trace comparison add overhead; no sample count is used as an
elapsed-time share or speedup measurement.

The twelve-variable sample contains a prominent normal-reduction path entering
`Engine::ordered_multiple` at return offset 348. Its recursive callees are
reported as deduplicated symbols by the sampler. The retained binary resolves
them to the shared libc++ introsort implementation:

- Sampled image UUID: `DA2444B8-53E1-362F-9A9A-F10DEECD0AB8`.
- Image load address: `0x1041f8000`.
- Repeated sampled address: `0x1041ff1c8`, image offset `0x71c8`.
- Introsort entry at image offset `0x69f8`; the recursive offset is 2,000 bytes.
- `ordered_multiple` calls it at image offset `0x5970`; return `0x5974` is
  exactly 348 bytes after that function's `0x5818` entry.

The compiler has merged identical comparator instantiations, so symbol aliases
can name either the normal or ordered-multiple comparator. The call-site
disassembly identifies the ordered-multiple sorting path directly. The sample
also contains substantial symmetric-difference merge work. Nine-variable
samples show packed-matrix work; the small solved case includes substantial
Python execution and independent checking/replay. Sampling does not justify
assigning one universal bottleneck to all three cases.

## Next representation hypothesis

Test integer sort keys that encode the current order for monomials using at
most 57 mask bits. An unsigned key

`((64 - popcount(mask)) << 57) | mask`

orders first by decreasing degree, then by increasing mask, exactly matching
the current descending grevlex comparator. Its degree prefix occupies at most
seven bits, and the mask occupies the lower 57. Decode with the 57-bit mask
before parity cancellation/output. Equal monomials have equal keys. Any
monomial outside that range must retain the existing comparator path.

This could remove repeated popcounts inside comparison sorting. It does not
change the asymptotic comparison-sort bound or establish a new Gröbner-basis
algorithm. Validate the order equivalence, high-bit fallback, cancellation,
exact work/proof traces and complete-query timing before promoting it.
