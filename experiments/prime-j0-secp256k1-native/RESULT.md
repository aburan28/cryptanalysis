# Native 256-bit cached-projective point-path replay

The Rust source, Sage fixture generator, dependency lockfile, and
protocol were frozen in commit `1b1c1532` before fixture generation.
The fixture was built through the checked repository Sage launcher,
whose saved runtime receipt reports `status: verified`. It contains
the 64 previously frozen one-use secp256k1 cases, nine independently
verified seeds per case, all width-four digit streams, expected scalar
points, and exact evaluator counts. Its SHA-256 is
`2e8da438343ecf650c9d8d9b2a593f5d603027c4c1f81485f2456c38028491d4`.

The standalone crate imports the repository's existing 256-bit
Montgomery field and fixed-width integer modules, then implements the
endomorphism-assisted Jacobian seed chain, unit orbits, cached seed
`Z²,Z³` powers, paired-τ strides, and final affine recovery. The
offline, locked release build succeeded on physical ARM64 macOS with
Rust `1.93.1`. The built binary SHA-256 is
`fa1ae3c5f1f0bb12b815f889b9eb6d17b3d17d6705e68cf28253ee04660f3510`.
Its run checked **576 native prepared seed points**, **64 native final
outputs**, and all saved stride, addition, and cache counts with no
mismatch. The full compiler, OS, source/fixture/binary hashes, build
command, raw stdout/stderr, exit codes, and replay summary are in
`native-replay-result.json`.

This verifies the **native point path on these nonzero cases**. Sage
still supplies the short `a+bτ` representative and digit stream, so
the binary does not yet implement the complete scalar-input method.
Zero, order-boundary, exceptional-addition, and secret-scalar safety
controls need separate coverage before production use. The local
host has no isolation receipt; no native CPU speedup was measured or
claimed. A full native recoder, stronger baselines, isolated timing,
and independent prior-art review remain required for the research
goal. `cpu_speedup_claim` and `academic_novelty_claim` are `null`.
