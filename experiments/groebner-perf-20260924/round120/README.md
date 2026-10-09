# Isolated replay of complete certified F4 queries

The manifest generator freezes five matched scratch-buffer versus bounded-bitset
queries with exact proof bytes, basis, assignment, producer work, checker work,
target, and field parameters. The worker reports the full `Context.run`
target-dependent interval, starting with fresh coefficient borrowing and ending
after independent proof, original-equation, and curve checks. It also emits
matrix, native F4, and checker phases. The proof digest check occurs outside the
online interval; both arms must still reproduce the frozen digest before a
result receives `verified=1`.

Build and audit both candidates on the physical Linux benchmark host from a
committed checkout. Use this repository's `round112/run_validation.py` to
create the reference audit and each candidate's `panel.py` to create its exact
optimized and UBSan panel. Then generate the host-specific manifest:

```sh
python3 experiments/groebner-perf-20260924/round118/build.py --reference-root "$PWD"
python3 experiments/groebner-perf-20260924/round119/build.py --reference-root "$PWD"
python3 experiments/groebner-perf-20260924/round118/panel.py --reference-report /absolute/reference/panel/report.json --output /absolute/scratch-panel
python3 experiments/groebner-perf-20260924/round119/panel.py --reference-report /absolute/reference/panel/report.json --output /absolute/bitset-panel
python3 experiments/groebner-perf-20260924/round120/make_isolated_manifest.py \
  --reference-root "$PWD" --validation-root /absolute/reference \
  --scratch-panel /absolute/scratch-panel --bitset-panel /absolute/bitset-panel \
  --python /absolute/python3 --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /absolute/bitset-isolated-manifest.json
python3 scripts/isolated_bench.py probe /absolute/bitset-isolated-manifest.json
```

CPU IDs, cgroup, Python path, and NUMA node above are examples; select them
from the host's topology and [isolation contract](../../../docs/ISOLATED_BENCHMARKS.md).
Only submit the manifest when the strict preflight passes. Keep the service's
raw failures, counter snapshots, paired run order, and correctness receipts.
The local macOS profile in `round119` remains an exploratory diagnostic.
