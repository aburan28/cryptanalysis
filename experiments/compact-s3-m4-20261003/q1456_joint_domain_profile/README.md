# Q1456: exact joint-pair domain profile on unpinned queries

Q1455's bounded joint join passes both partially freed witness controls,
but all observed N53/N83 unpinned partial states exceed its pair-candidate
cap. Q1456 measures the **exact** number of sparse completions in each
pair at every distinct state in short repeats of those same frozen CNFs.
It preserves Q1455's solver and decision rule; only domain instrumentation
is added. The result is a diagnostic of whether exact enumeration can
reasonably reach those states, not a successful-decomposition cost.

The [protocol](protocol.json) fixes the Q1455 archived N53 known-satisfiable
slice, full ordinary N53 target, and full ordinary N83 target, along with
curve IDs, exact factor-base counts and digests, workload IDs, compressed
CNF hashes, checked Sage runtime, binary/source hashes, and 15-second
diagnostic wall caps. This is proposal `Q1456`, `candidate_id: null`,
`run_id: null`, `isogeny: "none"`, stage code `PDP4hybrid`.

For each distinct partial state with all four leaves still partial and
neither pair intermediate fixed, the profiler counts every nonzero
normal-basis x completion within the weight bound. It records each pair's
completion product, a log-two histogram of the larger product, the minima,
and the full state list. The independent archive audit recomputes every
count from fixed-bit masks. A [pre-run control](control_result.json)
checks that the native profiler still returns both archived N53/N83
group-verified witness relations and that its state counts match the
separate Python implementation.

Use the accepted Sage launcher for the frozen checks:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/smoke.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/freeze_protocol.py --check
```
