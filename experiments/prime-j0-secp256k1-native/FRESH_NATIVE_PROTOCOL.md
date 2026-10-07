# Held-out native scalar-input replay

Freeze this protocol and `make_fresh_fixture.py` before deriving inputs.
Save the checked repository Sage launcher's `--runtime-info` output
first. Use eight deterministic, nonidentity secp256k1 bases and 32 new
deterministic full-width scalars per base, all under the fixed label
`prime-j0-native-full-heldout-20261007`. No prior fixture is used to
select these values. For each of the 256 cases, Sage independently
generates the short representative, width-four digits, nine prepared
seed points, native-path operation counts, and expected `kP`.

Run the already frozen native source from `98328303` against this new
fixture. Compare every native representative, digit stream, prepared
seed, count, and final point with the Sage record; retain raw exits,
source and fixture hashes, binary hash, and compiler/host details.
Preserve failures. This is held-out correctness only, with no CPU
speedup or novelty claim. Exceptional cached additions may surface as
explicit failures under the current formula.
