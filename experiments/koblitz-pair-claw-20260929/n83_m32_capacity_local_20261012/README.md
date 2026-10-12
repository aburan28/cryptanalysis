# Full M32 filter capacity on the fresh N83 minimum base

This experiment measures whether the frozen **23,859-orbit known-log base**
and a full `2^32`-descriptor, 15-bit Bloom table can coexist below an 8 GiB
process RSS cap. It uses the new public point from workload `1bd8900e972e`
and performs one query representative after table construction to exercise
the exact lookup and replay path. Relation yield from one query is not the
measurement objective.

The [protocol](protocol.json) binds the parent target and base receipts by
SHA-256, the exact affine table/query offsets, compiler source, memory cap,
and a 2,700-second wall limit. [run.py](run.py) compiles the same frozen native
source as the fresh-target smoke experiment, records the binary hash, and
observes child RSS every 50 ms with `ps`. It terminates the child if sampled
RSS reaches 8,589,934,592 bytes. The watchdog's sampled maximum and native
`peak_rss_bytes` are retained separately; a sampling interval cannot prove
that no shorter RSS spike occurred. The process runs on a local, unisolated
macOS ARM host, so CPU times are exploratory.

The full run completed under the 8 GiB RSS cap. The Bloom allocation was
8,053,129,216 bytes; native peak RSS was **8,213,069,824 bytes**, leaving
376,864,768 bytes below the cap. The 50 ms watchdog sampled a maximum of
8,212,873,216 bytes. Table construction took 1,856.56 s and the native
process took 1,857.82 s on the shared local host. The one query
representative generated 166 lifted pairs and completed exact replay with
zero positive lookup keys. Its bounded one-query outcome measures lookup
execution, not ordinary-query relation yield. A watchdog stop, timeout, or
native failure would be retained as its own terminal result. The
[verifier](verify.py) checks source and input bindings, terminal status,
exact M32 allocation, and both RSS measurements.

From a fresh directory on the same architecture:

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_m32_capacity_local_20261012/run.py
python3 experiments/koblitz-pair-claw-20260929/n83_m32_capacity_local_20261012/verify.py
```

The complete e2e factor-base comparison still needs all target-dependent
query waves, verified scalar recovery, a same-point rho reference, and a
qualified Tier 0 or Tier 1 host receipt. This capacity result decides
whether the 8 GiB M32 setup is viable for that next run.
