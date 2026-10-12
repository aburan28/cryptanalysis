# Fixed-width unit-orbit recoder: frozen comparison

The candidate changes only the online U14/U15/U16 coefficient recoder.
The current reference takes each signed coefficient remainder and exact
quotient with `BigInt` at every radix-256/512/1024 window. The candidate
loads the same lattice representative into two signed three-limb words,
takes the Euclidean remainder from the low limb, subtracts the same
Eisenstein digit, and shifts the exact quotient right by the window width.
It selects the same orbit and unit and uses the same precomputed point
table and point-addition sequence. The candidate remains opt-in.

For every format, run the existing and candidate benchmark case flags
from one release binary on fixture indices
`0,16,32,48,64,80,96,112,128`. Use five repetitions per index and the
isolated runner's alternating AB/BA order. Inputs, expected points,
binary, table, resource envelope, and online timer boundary are paired.
The executable loads the fixture, parses the scalar, and warms the
lattice, field constants, and selected fixed-generator table before the
online timer. It then includes scalar-dependent lattice reduction,
coefficient recoding, lookups, unit maps, point additions, final affine
conversion, and expected-point assertion. Preparation and process launch
are outside the interval. Report the common retained table size and
preparation cost separately.

Before manifest generation, the checker must replay all 129 fixture
points through each candidate benchmark-fixture flag, plus a direct
benchmark-case dispatch for each format and the corresponding reference
case. Verify expected points, metadata, table payload, and `verified=1`;
discard local timing values. Native tests must match the reference's
digit stream at every fixture window, check signed word boundaries, and
compare at least 256 fresh full-range scalars per format. Generate the
three manifests only from the binary and checker receipt with exact
source hashes. No wall-time improvement is accepted without a passing
host-isolation preflight, all correctness checks, and paired noise gates.
