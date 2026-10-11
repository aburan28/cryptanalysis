# Native promotion of the fixed-seed priority assignment

Promote the frozen `LP21` assignment with the same 67,338 seed points,
native evaluator, terminal atlas, and retained-byte count as the original
`rho0` candidate. Reindex its records into the same `DR20` binary format.
The materializer swaps only the full atlas and the fresh panel in the
already source-pinned native crate; Rust source hashes must remain equal.

Draw 4,096 new 256-bit scalars from the recorded Python PRNG seed and
reject any scalar whose subgroup residue occurs in an earlier panel,
including the original `rho0` native panel. Freeze the law and source
list before drawing. The native targeted test compares all outputs with
the direct-index and fused implementations, checks the first 128 by
independent binary multiplication, and reports paired mixed additions
and gauge rotations. Verify all direct-class records and residues, run
the complete native suite and edge fixture, and preserve source/input
hashes and raw status. Do not infer a runtime gain from local timing.
