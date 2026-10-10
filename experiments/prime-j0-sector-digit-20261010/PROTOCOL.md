# Piecewise canonical-sector digits for the U14 point-only table

Mode 130 retains the same fourteen four-limb affine point windows, scalar
representative, orbit rank, and grouped gauge as mode 129. Its single
algorithmic change is to choose the nearest signed digit of a canonical
unit-orbit representative with three interval tests instead of four
quadratic-norm evaluations. The exact intervals and tie convention are
proved in [PROOF.md](PROOF.md). Radices are `m=512` and `m=1024`.

Freeze this protocol, proof, implementation, and generator in a commit
before generating a new 4,096-scalar panel with seed `20261010130`.
Reduced scalar values must be unique and disjoint from the eleven earlier
U14 panels. Exhaustively compare mode 130 with mode 129 for every
`512²+1024²=1,310,720` residue pair, including digit, orbit rank,
and unit code. Independently compare all affine point-table entries,
all fourteen recoding choices on the new panel, all final points and
operation counters, and the first 128 points with binary multiplication.
Run both 129-case fixture arms and the full release suite. Preserve raw
outputs, exit codes, source/input/binary hashes, failures, and memory.

The online comparison is mode 129 versus mode 130 on the same public
scalar, after table preparation. Charge representative selection,
recoding, orbit/digit computation, point lookup, gauge additions,
inversion, formatting, and expected-point verification. Use the
repository's isolated Linux benchmark service, paired run order, and
noise gates before reporting a wall-time ratio. Local timing is
diagnostic. The remote serial runner can establish Linux correctness;
its container affinity alone does not establish host-wide isolation.
