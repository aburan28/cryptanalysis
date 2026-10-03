# Fresh independent preparation during basis production

Round53 separates original-input coefficient reconstruction from proof-dependent
certification. An opt-in worker can prepare the independent checker while the
unchanged round51 producer computes the basis. The prior round52 implementation
remains the comparator. This is an experimental scheduling change, with no
automatic backend promotion or measured speedup assumed.

`ProjectionQuery(..., preparation='serial')` preserves serial checking by default.
`preparation='prepared'` exercises the same split interface synchronously.
`preparation='overlap'` uses one additional CPU worker for one query. Both CPU and
Metal producers are supported; Metal remains explicitly requested. Existing
device capability checks and the portable CPU implementation are retained.

Each scheduled query copies its original typed packed input into owned buffers.
It does not construct polynomial sets, sort supports or reuse target answers.
The checker independently scatters and transforms those coefficients. Its native
state is bound to the exact mask width, term count, ordered masks, coefficient
words and checker generation. Configuration changes, serial certification or a
new preparation invalidate the pending generation. A prepared generation is
consumed once; stale, foreign or changed-input uses are rejected.

Input symmetry and proof symmetry remain independently checked. A proof-dependent
soft-budget failure can require the original full transform; in that case the
checker reconstructs it and records the additional preparation work. Existing
logical verification counters, rejection codes and work-budget failure points
are compared with round52. Preparation cannot replace root completeness, affine
rank, original equation, reduced-basis or curve-replay checks.

The scheduling lock serializes queries in each context. A query joins its worker
on success, inconclusive results and exceptions before buffers can be closed or
reused. Preparation failures retain their receipt; soft unsupported/budget exits
use the serial checker. Closing waits for active computation. Independent contexts
have independent workers and checker state.

The performance boundary wraps one complete `solve(public_point)` call. It
includes packed snapshots, preparation, all solving/checking, transfers,
synchronization, input binding, coordination, mandatory drain and direct equation
and curve replay. Reusable workspace/executor setup is outside. Every arm has
the same maximum resource allowance: two CPU query threads and the same GPU;
serial arms use only one thread. A concurrency win is not a reduction in total
CPU work. `specialization` reports accumulated checker work and must not be added
to overlapping producer timers. Whole-query wall time remains primary.

The frozen measurement plan compares the prior CPU/full-Metal/tiled-Metal paths
with new serial, synchronous-prepared and overlapped paths. All failures, rejected
load admissions and unrun trials remain in the evidence. Two qualified trials
on each of three 27-variable inputs must clear the paired interval gate against
every confirmatory comparator. A partial panel cannot promote automatic routing.
These are bounded polynomial/query stage diagnostics: `candidate_id` and complete
IC/rho `online_speedup` remain null.

Build dependencies through round52 using their existing build scripts, then run:

```sh
python experiments/groebner-perf-20260924/round53/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round53 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round53/validate_native.py --output correctness.json.gz
python experiments/groebner-perf-20260924/round53/audit_queries.py --input correctness.json.gz --output independent-audit.json
```

Use `--metal` for native validation when that backend has been built. CI rebuilds
native code on Linux x86-64 and macOS ARM64 and records the actual device. A hosted
paravirtual Metal device establishes correctness only, not physical M4 performance.
The native build records every source and binary hash; validation rechecks them
before and after execution. The separate Python audit loads no native solver or
checker and replays proofs against frozen original ANFs.
