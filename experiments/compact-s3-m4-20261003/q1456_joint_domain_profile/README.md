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

## Frozen 15-second profile

The [archive audit](verification.json) recomputes **every** archived pair
completion count and histogram from the fixed leaf bits. A separate
[post-run threshold audit](threshold_interpretation.json) counts how many
of those exact states each prospective cap would admit.

| Input | Distinct partial states | Smallest larger-pair domain | States admitted at cap 4,096 | Result |
| --- | ---: | ---: | ---: | --- |
| N53 known-satisfiable, unpinned | 21 | 1,300 | 6 | 15 s cap; no relation |
| N53 full ordinary target | 21 | 1,300 | 6 | 15 s cap; no relation |
| N83 full ordinary target | 23 | 3,081 | 1 | 15 s cap; no relation |

The current Q1455 caps of 256 at N53 and 1,024 at N83 admit zero of
these states. Raising both to 4,096 is a bounded, solution-preserving next
test because it would activate the joint rule in all three observed
prefixes. The profile does not predict that those checks will find a
relation; a new check changes the subsequent SAT path, and the larger
domains cost more exact `S3` root work and memory. Early states still have
much larger domains, reaching log-two buckets 36 at N53 and 57 at N83.
These are completion counts, not field-operation costs or a complete N131
projection. The host has no CPU-isolation receipt, so the diagnostic wall
times are exploratory.

Use the accepted Sage launcher for the frozen checks:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/smoke.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/verify_archive.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1456_joint_domain_profile/audit_threshold.py --check
```
