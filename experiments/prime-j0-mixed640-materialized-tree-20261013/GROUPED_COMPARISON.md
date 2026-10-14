# Grouped table versus pre-tau materialization

The existing two-bucket grouped-gauge evaluator was **1.563 times faster**
than the selective pre-tau table on one frozen scalar in a paired RunPod
Tier 1 panel. Both executables used the same mixed-radix 640 recoder and
returned the same independently checked point. The grouped table retained
31,302,596 bytes; the selective pre-tau table retained 67,010,468 bytes.
This result puts table footprint and selection traffic at the center of the
next scalar-multiplication design, even though the grouped path makes more
point-kernel calls.

| Case-0 panel | Valid pairs | Median selective/grouped online ratio | Paired bootstrap 95% interval | Median online time, selective/grouped | Median preparation, selective/grouped |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selective pre-tau versus grouped gauge | 8/8 | 1.5634 | 1.4701–1.7559 | 0.07437/0.04727 ms | 10,540/5,306 ms |

`native_grouped_bench.py` generates the grouped front door from the same
source-pinned crate and fixture as `native_bench_cli.py`. The timer starts
before the target-dependent multiplication call and ends after affine
point recovery. It includes recoding, lookup, unit selection, bucket
evaluation, tau, final addition, and recovery. Table preparation and the
fixture equality check are recorded outside the online interval. The
existing grouped evaluator's 4,096-scalar Linux test passed, with
independent binary checks on its first 128 inputs. The new benchmark
front door also verified the frozen case-0 point.

All sixteen timed invocations and eight pair rows were valid. Source,
runner, and binary hashes stayed stable; raw counters, failures fields,
manifests, preflight, and outputs are in
`tier1-runpod-20261013/e78ec647409243519a3f59dfb6025c9e/`. The
transferred archive SHA-256 was
`be9ebd656f775a36580d3eb88e5289d988e2afb7da5ea4590158c389c8ed391b`.
The grouped binary SHA-256 was
`949ec1eb0c06da9cfd5a93362c4c68c4aaa513be4fd228ace3e7630df9da95b9`.
The Pod supplies instance-scoped Tier 1 evidence; its preflight does not
prove host-exclusive CPU ownership. The result measures one scalar, and
table size is a plausible cause rather than an isolated causal variable:
the two methods also differ in addition schedule and tau handling.

The next measurement uses eight other frozen holdout scalars, with five
paired repetitions each, submitted as separate jobs to the single serial
worker. An attempted combined eight-case manifest was rejected before
execution by the pinned runner's one-case schema. The updated
`make_tier1_manifest.py` emits one valid manifest per case, preserving
one-case job receipts and serial execution. The 17.5 MB fifteen-window
format is the next matched table-size point; `native_frontier15_bench.py`
generates its benchmark front door.
