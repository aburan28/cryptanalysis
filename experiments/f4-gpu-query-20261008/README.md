# Complete F4 query CPU/CUDA crossover panel

`suite/examples/f4_query_bench.rs` times one target-dependent point-decomposition
query: target conversion, Boolean system construction, algebraic splitting/F4,
independent evaluation of every returned root against the original equations,
and lifting summand abscissae to curve points whose sum matches the target.
The solver's CUDA offload runs inside that interval, including matrix upload,
kernel launches, synchronization and download. Curve and factor-base setup is
recorded as reusable setup outside the online interval; JSON artifact writing
is outside it as well. The work is a stage query and does not substitute for
the repository's single-target IC/rho metric.

The panel uses the same compiled binary and input law for host and CUDA arms,
alternates AB/BA order, retains failures and timeouts, requires identical
accepted assignments and curve checks, and confirms CUDA actually ran before
reporting an exploratory pair. `F4_F2_ECHELON_MIN_WORDS=1` forces eligible
matrices to the device so the one-query transfer and launch cost is visible.
`qualified_speedup` stays null until a full matched device and host resource
receipt satisfies the relevant gate. Queries with a node or solution cap are
recorded under that status and do not enter a speedup ratio.

On a CUDA host:

```sh
cloud/runpod_pod.py run f4-query \
  --out experiments/f4-gpu-query-20261008/receipts/new -- \
  'bash experiments/f4-gpu-query-20261008/pod_query_ab.sh experiments/f4-gpu-query-20261008/receipts/new'
```

For a host-only integration check, build the example and run `query_ab.py`
with `--sides host`. Keep compiler, device, source hash, target cell, F4
degree, node/solution caps, matrix count, and raw logs with every result.
