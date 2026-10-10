# Two-limb radix-384 quotient for Eisenstein scalar recoding

Mode 134 keeps mode 133's certified scalar representative, fifteen
radix-384 unit-orbit windows, 24,578-point atlas, point tables, and
grouped unit gauge. It changes only the signed-word quotient and
remainder calculation. The primary comparison is mode 133 on identical
public scalars; both modes retain 24,283,336 bytes and have the same
point-operation counts.

The hypothesis is that the quotient of a certified coordinate by
`384 = 3*128` can be obtained with two 64-bit divisions by the constant
three, instead of six 32-bit chunk divisions by 384. The compiler's
reciprocal-multiply lowering and the complete online cost, including
representative selection, recoding, lookup, point additions, inversion,
formatting and point verification, must be recorded before any timing
claim. A local or container timing ratio remains exploratory without
the strict isolation receipt in `docs/ISOLATED_BENCHMARKS.md`.

Freeze this protocol, proof, generator, implementation and division tests
in a commit before generating a new disjoint 4,096-scalar panel with seed
`20261010135`. Check signed quotient/remainder against the generic
implementation at limb boundaries and on all panel recoding steps.
Compare modes 133 and 134 on the new panel, all 129 fixed fixture points,
and the first 128 panel points against independent binary multiplication.
Preserve the full release suite, source/input/binary hashes, raw failures,
and operation counts. The RunPod queue may provide a serialized Linux
correctness replay; its current container does not qualify for a
controlled CPU speedup result.
