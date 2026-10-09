# Unit-orbit windows against fixed-base GLV10: frozen CPU protocol

Compare the repository's ten-row fixed-base GLV comb with U14, U15, and
U16 in three separate paired manifests. Each command multiplies the same
public scalar by the standard secp256k1 generator. Use fixture indices
`0,16,32,48,64,80,96,112,128` from
`tau6-comb13-bench-fixture.json`, five repetitions per index, and the
isolated runner's alternating AB/BA order. The first eight indices are
sampled from the prior holdout; index 128 exercises the declared fallback
case. Build one Linux release binary from one source snapshot for both
methods. Do not change the fixture, flags, order, or repetitions after
examining timing data.

The benchmark executable loads the fixture, parses the scalar, and warms
the selected fixed-base table and lattice constants before the online
interval. The monotonic timer starts immediately before target-dependent
scalar decomposition and stops after the final affine conversion and
expected-point assertion. It therefore includes the GLV or Eisenstein
recoder, every lookup, unit action, point operation, and output check.
Table construction, process launch, and input loading are excluded.
Report the preparation cost and retained table size separately when
available. The GLV10 reference stores 1,024 subset entries; U14/U15/U16
store 1,004,904/458,772/207,552 point slots respectively, plus their
residue maps. The comparison asks whether the larger precomputed tables
improve one-scalar online time in a common resource envelope.

Before generating manifests, replay the GLV10 benchmark case CLI on all
129 fixture points and bind its receipt to the same binary and U14/U15/U16
checker receipt. Each output must match the fixture point and say
`verified=1`. The checker discards its local timing values. The manifest
generator verifies source, binary, fixture, and both receipts. Run the
strict host preflight before queue submission. A rejected preflight is a
retained environment result; it cannot support an online speedup ratio.
Preserve raw failures, and treat a candidate as faster only when all
required pairs pass the isolation, noise, and correctness gates.
