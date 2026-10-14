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

The serial eight-case panel completed on holdout cases 1, 17, 33, 49, 65,
81, 97, and 113, with five valid pairs per case and 80 valid timed
invocations. The median of the eight case medians was **1.6233**; the
case medians ranged from **1.5426 to 1.7191**. A 20,000-replicate
hierarchical bootstrap, resampling cases and then pairs within each case,
gave **1.5324–1.6941** for the median of case medians. All eight job
summaries report stable artifacts, binaries, and runner, with no invalid
runs. The raw receipts and computed panel row are under
`tier1-runpod-20261013/`, with panel metadata in
`grouped-eight-panel.json`; the transferred archive SHA-256 is
`6e639e31a99b062e7395a1643f7475b6a816f70887145fd3921ded8c86dffeef`.
This remains instance-scoped Tier 1 evidence because host exclusivity was
not proved.

An attempted combined eight-case manifest was rejected before execution
by the pinned runner's one-case schema. The corrected
`make_tier1_manifest.py` emitted one valid manifest per case, preserving
one-case receipts and serial execution. The 17.5 MB fifteen-window format
and the new axial factorization are the next matched table-size points;
their generators are `native_frontier15_bench.py` and
`native_axial_bench.py`.

Both case-0 comparisons completed with eight valid pairs on the same
serial service. The grouped/frontier-15 median online ratio was **1.0462**
with paired interval **0.9530–1.2021**. The grouped/axial median was
**0.9709** with interval **0.9533–1.0324**. The three retained table sizes
are 31,302,596 bytes (grouped), 17,511,596 bytes (frontier-15), and
5,746,628 bytes (axial). The frontier-15 raw job is
`tier1-runpod-20261013/a2cacbfd752348559df2608a3bced45e/`; its
transferred archive SHA-256 is
`9bf1ae05771d4638d0adb9b2ab1eea157a387d500c613304c7cb767f68335b48`.
All sixteen timed invocations in each job were valid, and all artifact,
binary, and runner stability checks passed. Their intervals include one,
so case-0 online ordering among these three formats remains unresolved.
Each receipt records `host_exclusivity_proved=false`.
