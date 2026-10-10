# Frozen six-distinct-leaf projective-S3 control

The [single-coordinate frontier](../ecc2k130-263-leaf-inverse-frontier-20261010/RESULT.md)
found a fast leaf-0 x solve on both curves, but each SAT assignment recalled
the same cancelling first pair and identity intermediate as its parent
witness. This control replaces that exceptional fixture with the six ordered,
distinct W24 leaves already checked in the
[native-geometry archive](../ecc2k130-263-native-w24-m6-20261010/runs/R1/geometry_controls.json).
The archived six rows per curve are selected by indices `[0,1,2,3,4,5]`;
no new base enumeration or outcome-dependent search is permitted. Their raw
sum with all-plus signs defines one new control target per curve. These
synthetic control targets are separate from the held-out public Q1420 target.

Before any solver run, independently check the six raw points and all pair,
four-leaf, and six-leaf sums with Sage and the polynomial-basis group law.
Require distinct selected masks and raw x coordinates, all intermediate
states finite, five projective S3 links zero, six distinct nonidentity
fourfold-projected points with `r[4]P=0`, and the frozen exact target point.
Use the repository Sage launcher and save its checked runtime-info receipt.

Build one native-XOR XCNF per curve from the pinned projective-S3 encoder,
using the four target-mux x choices `(target_x, target_x xor 1,
target_x xor 1, target_x xor 1)`. Preserve the full base XCNF losslessly
in deterministic gzip, its named-input map, source hashes, raw formula hash,
and resource receipt. Derive six exact unit-clause deltas per curve:

1. `positive`: fix six masks, all leaf x/z words, all four projective states,
   and target choice zero; require verified SAT and signed exact-target replay.
2. `negative`: retain those fixed witness inputs and select choice one;
   require explicit UNSAT.
3. `x0`, `z0`, `x5`, `z5`: start from the positive units and release exactly
   the named 131-bit leaf-coordinate word. Every other external bit stays
   fixed. A SAT model must pass every ordinary clause/native XOR and exact
   signed group replay; a capped search remains `BOUNDED_UNKNOWN`.

Commit this protocol, configuration, producer, and independent auditor before
constructing the witness. Commit the checked witness, base-formula archives,
input maps, exact unit deltas, and complete full-input hashes before launching
the first solver cell. Run the twelve cells once in the `CONFIG.json` order.
Use CryptoMiniSat 5.14.7 native-XOR mode, one thread, `--printsol=1`, an
internal wall limit of 45 seconds for fixed controls and 120 seconds for
released-coordinate cells, a respective external guard of 60/150 seconds,
and a 4-GiB sampled-RSS guard. Save lossless stdout/stderr, process exit,
guard status, actual wall/RSS, printed conflicts, and restart progress.

The primary decision is whether the earlier x0/z0 split persists with a
finite, noncancelling witness. A failure of the positive/negative controls
invalidates the coordinate comparison. If all four releases now stall on
both curves, prioritize the exceptional-state shortcut and a targeted leaf
inverse propagation experiment rather than promoting the earlier x0 time.
If one coordinate consistently solves, test a compact selective inverse
encoding on this same frozen input before opening an ordinary query. Only a
verified ordinary relation permits the equal-B yield and novel-rank gate.
`candidate_id`, natural relation yield, rank, online IC time, and matched rho
ratio remain `null` for this fixture control. Host-wide CPU isolation is
unverified, so wall times are exploratory solver-stage diagnostics.
