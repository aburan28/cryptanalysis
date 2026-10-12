# Owned proof transport experiment

Round103 tests whether Python proof-node allocation is a material part of the
complete query after round102's bounded bitset checker. Numerical producer and
checker sources are unchanged. The opt-in `matrix-packed` arm copies the already
certified native proof into immutable Python `bytes` while its native result is
alive. It returns an `OwnedProof`; no native pointer survives result cleanup.
`matrix-list` preserves the existing Python-list output. F4 hash/dense arms remain
reference controls. This changes the experimental output API, not production defaults.

Certification, basis materialization, proof ownership transfer, extraction,
independent equations/curve replay and lease teardown stay inside the query
timer. `materialization` records basis/proof subtimes inside that same interval.
Serialization, content hashing, artifact storage and optional native-free
binary-to-list decoding happen afterward. The worker reports serialization and
decoding times separately. A consumer that requires lists must also pay the
decoding cost; a packed-output result is not an unchanged-list-API timing claim.
Process peak RSS includes setup, artifact conversion and decoding.

The frozen 13-case panel retains round102's producer/checker budgets, every
failed attempt and fallback, one warmup and four rotated observations. Planted
PDP controls establish correctness only, not natural relation yield or a full
discrete-log result. This CPU-only host is not isolated: qualified, aggregate and
IC online speedups remain null regardless of diagnostic wall times. See
[PROTOCOL.md](PROTOCOL.md) for format and acceptance details.

From a committed source tree, run with Python 3.13:

```sh
python3 experiments/groebner-perf-20260924/round103/run_validation.py --output /absolute/new/evidence --diagnostics
```

The validation runner holds the shared heavy-work lock, verifies frozen sources,
builds optimized and UBSan libraries freshly, runs unit/negative controls, audits
all 104 control cells, then records and audits the 260-cell diagnostic panel.
CI omits diagnostics and builds independently on Linux and macOS. The audit
loads no native library, decodes the binary format independently of the writer,
checks exact proof equality with the list reference, and verifies ideal equality
and Boolean Gröbner completion from original equations.
