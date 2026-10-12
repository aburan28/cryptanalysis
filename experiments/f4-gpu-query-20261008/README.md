# Complete F4/F5 query CPU/CUDA crossover panel

`suite/examples/f4_query_bench.rs` times one target-dependent point-decomposition
query with either matrix F4 or signature-filtered matrix F5: target conversion,
Boolean system construction, algebraic splitting and matrix reduction,
independent evaluation of every returned root against the original equations,
and lifting summand abscissae to curve points whose sum matches the target.
The solver's CUDA offload runs inside that interval, including matrix upload,
kernel launches, synchronization and download. Curve and factor-base setup is
recorded as reusable setup outside the online interval; JSON artifact writing
is outside it as well. The work is a stage query and does not substitute for
the repository's single-target IC/rho metric.
Each JSON result records the field modulus, curve and subgroup orders, cofactor,
actual factor-base point count, dimension and basis, engine, target, and limits.
The four exclusive `phase_ns` fields sum exactly to `online_ns`: target
conversion, system construction, solve including independent callbacks, and
offload bookkeeping. Callback time is also reported as a subset of solve time.
The `algebra` snapshot records Macaulay build, reduction, readback, matrix
shape, and F5 criterion work for the same query. This exposes whether the
next F4/F5 optimization belongs in symbolic construction, elimination, or
signature filtering.

The panel uses the same compiled binary, engine, and input law for host and CUDA arms,
alternates AB/BA order, retains failures and timeouts, requires identical
accepted assignments and curve checks, and confirms CUDA actually ran before
reporting an exploratory pair. `F4_F2_ECHELON_MIN_WORDS=1` forces eligible
matrices to the device so the one-query transfer and launch cost is visible.
`qualified_speedup` stays null until a full matched device and host resource
receipt satisfies the relevant gate. Queries with a node or solution cap are
recorded under that status and do not enter a speedup ratio.
The default `0:9:2` cells use target abscissae `12`, `14`, and `22`, the first
three verified-positive points in a deterministic scan from `0` to `40`.
This selection makes the GPU path exercise completed decompositions; it is a
correctness control rather than a relation-yield sample.

On a CUDA host, `pod_query_ab.sh` runs both engines in separate `f4` and `f5`
subdirectories:

```sh
cloud/runpod_pod.py run f4-query \
  --out experiments/f4-gpu-query-20261008/receipts/new -- \
  'bash experiments/f4-gpu-query-20261008/pod_query_ab.sh experiments/f4-gpu-query-20261008/receipts/new'
```

For a host-only integration check, build the example and run `query_ab.py`
with `--sides host`. Keep compiler, device, source hash, target cell, F4
degree, node/solution caps, matrix count, and raw logs with every result.
