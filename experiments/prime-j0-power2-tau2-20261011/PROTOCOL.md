# Three tau images per seed in twelve radix-1024 shift windows

This candidate keeps the certified secp256k1 representative, twelve
radix-1024 quotient shifts, and the exact terminal norm disk from the
power-of-two residual format. It changes the atlas cover: one stored seed
may represent its own six-unit class and as many as two successive tau
images. The full-window decoder stores an exponent in `{0,1,2}`. A
three-bucket point evaluator computes `B0 + tau(B1 + tau(B2))`.

For a full-window residue class `v`, let `d_v` be its minimum-norm integer
representative. A seed at `v` may cover one class unconditionally, two
classes when `3 N(d_v) <= 1024^2`, and three classes when
`9 N(d_v) <= 1024^2`. The tau permutation decomposes the 174,764 unit
classes into cycles. For each cycle, compute a minimum-cardinality
partition into admissible forward segments of length one, two, or three.
An exact dynamic program checks each possible segment start covering a
fixed origin and reconstructs the selected segments.

The terminal disk remains `N(a,b) < 149^2`. Its nonzero unit classes form
finite tau chains. A seed may cover up to three consecutive classes while
the corresponding tau images remain inside the disk. Each chain of length
`L` therefore uses `ceil(L/3)` seeds, with one additional identity seed.

The preliminary exact graph screen found 73,417 full-window seeds and
9,288 terminal seeds. Twelve full rows and one terminal row would contain
890,292 affine slots, or 56,978,688 bytes of point payload. These are
screening figures until the generated binary atlases and an independent
verifier certify every code and minimum seed count.

Freeze the generator, proof, atlas bytes, independent verifier, and scalar
input law before drawing a panel disjoint from all earlier panels. Check
integer reconstruction, decoded terms, three-bucket group evaluation,
and independent scalar multiplication on the full panel. Pair the
radix-1024 two-bucket control on that same panel. Count all extra tau and
point operations, table bytes, and recoder costs. A CPU wall-time ratio
requires the host isolation receipt in `docs/ISOLATED_BENCHMARKS.md`.
