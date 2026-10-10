# Cache-sized point-only U15 and U16 scalar tables

This experiment changes the window schedule of the point-only U14
Eisenstein scalar evaluator while preserving its nearest-sector digit,
six-unit orbit quotient, certified scalar representative, four-limb
field arithmetic, and grouped accumulator gauge. The primary baseline
is mode 130 with widths `[10,10,10,9*11]`. Candidate mode 131 uses
`[8*6,9*9]`, and mode 132 uses `[8*15,9]`. Each schedule totals 129
bits and has no online point doubling or `tau` step.

The observed Linux host reports a 32 MiB L3 cache shared by CPUs
`0-7,16-23`. This motivates the cache-fit hypothesis: mode 130's
64,314,112-byte table exceeds that group, while the predicted mode 131
and 132 tables are 29,361,680 and 13,283,616 bytes. The extra
worst-case mixed additions are one and two. Cache fit is a design
prediction, not a measured speedup or evidence of host-wide isolation.

Freeze this protocol, proof, implementation, and input generator in a
commit before generating a new 4,096-scalar panel with seed
`20261010132`. Its reduced values must be unique and disjoint from
all twelve preceding panels. Exhaustively check all 65,536 radix-256
residues against the stored orbit atlas, including signed digit, orbit
rank, and unit code. For every new scalar, compare U14, U15, and U16
points, representatives, all recoding choices, operation counts, and
the first 128 points against independent binary multiplication. Check
every independently built affine table entry, all 129 fixture points
per mode, and the full release suite. Preserve source/input/binary
hashes, raw outputs, failures, and process RSS.

The primary online comparison pairs one previously unseen public
scalar in mode 130 against mode 131, then mode 132, after each mode's
table preparation. Charge representative selection, recoding, lookup,
unit grouping, additions, final inversion, formatting, and expected
point verification. Keep both candidate rows, including any losing
or failed run. A controlled wall-time ratio requires the isolated
Linux host service with passing preflight and noise gates. The RunPod
serial runner checks Linux correctness and prevents overlap among our
jobs; container affinity alone is insufficient for CPU speed claims.
