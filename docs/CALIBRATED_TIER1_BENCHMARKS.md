# Calibrated Tier 1 CPU benchmark service

`scripts/calibrated_tier1_bench.py` runs the existing serial queue and worker
lock from `scripts/isolated_bench.py`. For every paired comparison it runs the
same deterministic calibration executable twice before the pair and twice
after it. The four runs use the benchmark CPU affinity and cgroup. They must
all pass the runner's output and noise checks, return the frozen output, and
have `max(online_ms) / min(online_ms) <= 1 + max_spread_bps / 10000`.

The manifest must include the calibration executable and wrapper in
`artifacts`, plus a `calibration` object such as:

```json
{
  "argv": ["/absolute/path/tier1_calibrator.py"],
  "expected_fields": {
    "calibration_id": "sha256-32m-v1",
    "digest": "b4ce437f949765dce16ec0d6c6b7c5a1d4ef209874ce9f04ee42984c06f14b40"
  },
  "max_spread_bps": 500,
  "timeout_s": 30
}
```

Freeze the spread limit before submitting work. The bundled calibrator hashes
32 MiB of deterministic data and reports its internal elapsed time. Its
digest checks that each invocation did the same work. The four calibration
rows, their raw stdout/stderr, and their pair verdict remain in each job
folder. Every solver row records UTC and monotonic attempt start/stop times.

Start the service on the target pod or host with:

```sh
python3 -u scripts/calibrated_tier1_bench.py --queue-root /durable/queue serve
```

Use `probe`, `submit`, and `status` from the same script. Start only one service
for a queue. The queue's worker lock rejects concurrent workers, including
an older `isolated_bench.py` service. Keep the allocation receipt, source and
binary hashes, input fixture, resource limits, cgroup evidence, and raw job
folders. Do not alter a manifest after submission.

Each one-case job is a stage record. Run at least five distinct frozen public
points, with at least five alternating reference/candidate pairs per point,
then check their job folders with:

```sh
python3 scripts/tier1_panel_check.py /durable/queue/jobs/<job1> ... /durable/queue/jobs/<job5>
```

The panel checker requires the same allocation, binaries, calibration rule,
runner, and resource envelope; complete valid pairs and A/A receipts; and
monotonic timestamps. A speedup is promoted only if every point's median
reference/candidate ratio exceeds one and the point bootstrap lower bound
exceeds one. Preserve invalid or noisy jobs as failed observations. A Tier 1
pod record describes the exposed cloud allocation; physical host exclusivity
requires the separate Tier 0 gate in `docs/IC_BENCHMARK_TIERS.md`.

The result field and frozen expected point in each manifest are checked by
the serial runner. For scalar multiplication studies, additionally replay
the scalar-to-point equality independently when archiving the panel; the
generic panel checker cannot infer a curve from arbitrary output fields.
