# Dense proof buffer reuse experiment

Round104 tests whether repeated allocation of dense XOR values is a significant
part of independent certificate checking after round103's owned proof transport.
The frozen MQ12 proof contains 68,052 XOR nodes; 68,047 have a distinct operand
consumed for the last time at that node. All proof nodes are reachable, so simple
reachability pruning provides no reduction on this panel. These are static
observations, not speedup measurements.

The opt-in candidate transfers one such operand's word buffer to the XOR result.
It retains the operand's logical term count until ordinary reclamation. Uses
include future operations and output checks. Aliased operands, nonfinal uses,
and the keep policy use the existing allocating implementation. The original
CPU checker and large-ring sparse fallback remain available.

`f4-dense` / `f4-reuse` compare identical F4 producers and list output;
`matrix-packed` / `matrix-reuse` compare identical leased Macaulay producers and
owned binary output. No paired arm changes its proof-output API. Producers,
proof DAGs, conservative work charges, term liveness and independent curve replay
must agree. Physical payload allocation/transfer/release counts and peak bytes
are checked by a separate native-free ownership simulation.

The complete query includes fresh coefficients, production, independent native
certification, proof ownership, extraction, independent equations/curve replay
and teardown. Reusable setup, serialization/storage and optional binary decoding
remain separately reported as in round103. The inherited `word_work` field is
a conservative charged-work counter: it includes initialization charges even
when transfer avoids that initialization. It is not an executed-instruction count.

The 13-case plan retains all failed/inconclusive attempts and fallbacks. These
CPU-only planted controls do not establish ordinary relation yield, a full IC
result, GPU performance, generic F4/F5 leadership or an asymptotic improvement.
Qualified/aggregate/IC online speedups stay null without the required isolation
receipt. See [PROTOCOL.md](PROTOCOL.md) for the ownership contract.

Run from a committed tree with Python 3.13:

```sh
python3 experiments/groebner-perf-20260924/round104/run_validation.py --output /absolute/new/evidence --diagnostics
```

The runner holds the shared heavy-work lock and binds all executed sources,
builds both checker variants with optimized and UBSan settings, runs correctness
and corruption controls before the frozen timing panel, and retains raw proofs
and failed rows. Linux/macOS CI rebuilds independently and omits timing claims.
