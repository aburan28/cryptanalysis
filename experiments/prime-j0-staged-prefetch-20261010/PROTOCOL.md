# Staged lookup and prefetch for fixed-base unit-orbit multiplication

The candidate separates fourteen signed-word U14 digit decisions from
point accumulation. During recoding, it records each `(orbit_id,unit)`
on the stack and issues read-prefetch hints for the selected 72-byte
affine table entry. After all digits are fixed, it loads the entries in
window order, applies the same unit maps, and executes the same mixed
additions as the original U14 signed-word evaluator. The candidate
uses the same secp256k1 generator, lattice selector, atlas, table, field
arithmetic, and final correctness check. Only the ordering of recoding,
memory hints, and point work changes.

## Frozen gates

1. Add a separate opt-in mode, `unit_orbit_staged14_fixed`, in the same
   release binary as the `unit_orbit_word14_fixed` reference. Keep the
   ordinary U14 path and automatic routing unchanged. Issue prefetch
   hints only to valid selected table entries, at byte offsets zero and
   64. Use stable x86-64 SSE prefetch, AArch64 `prfm` assembly, and a
   correctness-preserving no-op fallback on other targets.
2. Preserve exact scalar representative, fourteen digit/lookup choices,
   nonidentity count, retained table bytes, and final point for every
   compared scalar. Record zero selections and failures. Neither arm
   allocates a per-scalar heap object. The staged mode uses a fixed
   stack array of at most sixteen choices.
3. Pass the native release tests, the 129 independent fixed-generator
   fixture points in both modes, and all 519 frozen scalar inputs
   against the reference. Also compare at least 128 fresh scalars to
   independent binary double-and-add. Retain source, binary, input,
   command-output, and exit-status hashes in a checker receipt.
4. Generate a same-binary paired isolated-service manifest using nine
   frozen fixture indices `0,16,...,128` and five repetitions. The
   online timer includes scalar reduction, lattice selection, recoding,
   prefetch hints, table loads, unit actions, point additions, final
   affine conversion, and expected-point verification. Table creation
   and process launch are separate preparation. Promote a CPU ratio
   only when the strict host and noise gates pass; a contended local
   execution can establish correctness and dispatch only.

The candidate is a memory-latency hypothesis. Its operation count is
unchanged, and prefetch hints may be ignored by a CPU. The measured
question is whether overlapping table fetches with remaining recoding
reduces complete online time on an isolated physical host.
