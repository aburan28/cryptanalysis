# Unit-orbit positional windows: frozen online timing protocol

## Paired operation

Compare U14 to U15 and U14 to U16 in separate manifests. Each command
multiplies one public scalar by the standard secp256k1 generator using a
precomputed fixed-base table. The nine fixture indices are
`0,16,32,48,64,80,96,112,128` from
`tau6-comb13-bench-fixture.json`. The first eight are sampled random
scalars from the fixture's prior holdout panel; index 128 is its
deliberate fallback case. Use five repetitions per index, with the
isolated runner's alternating AB/BA order. The paired workload and
expected point are identical for both variants. Generate both
manifests from one code snapshot and one Linux release binary, changing
only the CLI method flag.

The executable loads and checks the fixture, parses the scalar, and
initializes the lattice, field decoding constants, and selected point
table before the online interval. Its monotonic clock starts
immediately before target-dependent scalar decomposition and stops
after final affine conversion and the expected-point assertion.
Report that interval as `online_ms`; report preparation time and
retained table payload separately. Process launch and table setup are
outside `online_ms`. The executable emits the curve, generator,
scalar, point, method, and `verified=1` only after the assertion passes.
The runner checks those fields against the frozen fixture and records
raw output, failures, host counters, binary hashes, and paired order.

## Promotion gate

Build and check the release binary on the selected Linux host. The
manifest generator must verify its source and correctness receipt,
complete fixture, and executable paths. Replay all 129 fixture cases
through each new benchmark CLI mode before submitting a timing panel;
those local checks are correctness tests only. Submit the manifests to
the serial service only after `probe` passes the strict host-level
isolation preflight. Preserve any rejected or invalid rows; aggregate
online speedup remains unknown unless every required pair verifies
and passes the runner's noise gates. U15 and U16 remain opt-in until
the paired online panel supports a routing decision.

The existing RunPod CPU Pod fails this host-level preflight, so it is
available for correctness checks but cannot yield a controlled CPU
timing result under this protocol.
