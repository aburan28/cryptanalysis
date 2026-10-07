# Leased native seeded queries

This opt-in API connects round110's native continuation to the ordinary leased
query boundary. When the matrix basis fails independent completion checking,
F4 continues from that basis plus every original equation. The composed proof is
checked against the original input before a result can be marked verified.
The native matrix, F4, composition and checker kernels are unchanged.

`seeded_query.Query.compute` preserves live input leases, query-owned layout
locks, fresh coefficients and shared producer/checker budgets. The matrix proof
remains alive throughout the continuation call. All handles are released before
return; `export_proof=True` returns the existing `OwnedProof` binary envelope.
No Python proof graph or intermediate continuation graph is materialized on
this query path. Omitting a layout uses fresh F4. `fallback=False` disables
continuation and fresh fallback after a matrix attempt.

```python
from seeded_query import Query, abi

query = Query()
equations = [[1, 6], [2, 5]]
coefficients = abi.anf_from_equations(equations)
workspace = query.workspace(3, 2, list(coefficients))
with query.layout(3, 2, 2, 0) as layout:
    with workspace.borrow_mapping(coefficients) as packed:
        result = query.compute(packed, layout=layout, export_proof=True)
assert result['verified']
owned_certificate = result['proof']  # Valid after both contexts have exited.
```

The basis is materialized separately from the certificate copy. Per-call phase
times cover matrix work, native seeded production, fresh F4, independent
checking, basis materialization, proof copying, teardown and residual overhead.
Their sum is the API wall interval. Native seeded production still combines
bridge/scan, F4 and proof composition; its internal split is not measured here.

From the repository root, run:

```sh
python3 experiments/groebner-perf-20260924/round111/run_validation.py --output /absolute/new/evidence-directory
python3 experiments/groebner-perf-20260924/round111/profile.py --output /absolute/new/profile-directory
```

Validation builds all 28 native libraries for the local platform, exercises the
API in optimized and UBSan modes, runs the frozen thirteen-case panel, replays
proofs and Boolean bases without native arithmetic, verifies curve solutions,
and rejects twelve corrupted artifacts. `--reuse-build` is an explicitly
recorded local option for existing source-matched round108/110 builds. CI does
fresh builds on Linux x86-64 and macOS ARM64. Python source files must be committed
before a recorded run. These commands use ordinary CPython; they do not use Sage.

Profiling uses one warmup and four paired observations per interface, ordered
AB/BA/BA/AB. It retains every failed or inconclusive row. Library, fixture and
reusable layout preparation stay outside the query interval. Each query gets
fresh coefficients, solving and independent native certification. The normal
API's complete-query adapter also replays both the current packed equations and
the independently generated original equations on the curve. The round110
diagnostic reference performs one original-equation/curve replay and exports
diagnostic Python proof graphs. This is an explicit interface comparison, not a
matched-output-format kernel speedup claim.

All measurements here are CPU-only stage diagnostics on small frozen algebra
and planted PDP controls. They are not IC end-to-end measurements, natural
relation-yield estimates, GPU measurements, or an asymptotic F6 result.
`qualified_speedup` remains null without an accepted isolation receipt.
See [RESULTS.md](RESULTS.md) for the complete panel and next engineering target.
