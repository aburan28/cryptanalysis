# Run report: full-subgroup E / genus-two image comparison

Commands: `cover_rho calibrate` on both pinned n=83 public jobs,
`cover_rho reference-suite` on eight a=1 public targets, and the uncapped
`cover_rho run` on both subgroup orders. The [protocol](../../PROTOCOL.md)
was committed before target generation; the [commands](../../RESUME.md)
identify the live worker and exact continuation. Reference source is
crypto d38a85f7e1ac02358223b58d71633f71f2efa7fa; resumable source is
dbd33f00da0a0ac35f285603ec168ad9d91a1d79. Public jobs retain every seed/hash.

At the acknowledged archival pause (Unix 1792005707), 27 optimized full a=1
runs were verified across eight independent targets; ten additional resumable
runs were verified. Only one native-Jacobian target is complete. Repeated
controls and representations do not add independent target instances.
For a=1 Q_0, all three resumable arms took exactly 6,631,641 steps:
E 5.845604437 s; inverse-image-to-E 5.842078086 s;
checked Cantor plus conversions 669.526079432 s. Every candidate passed a
separate-process check in E and J(C). The first paired optimized searches
were 2.741946817 s and 2.747020538 s. These are measured search wall times;
setup, transfer, checkpoint and verification observations remain separate.
No complete priced end-to-end cost or speedup is admitted.

The a=0 archived checkpoints contain 46,043,619 elliptic steps,
45,198,832 image-inverse steps and 459,379 native-Jacobian steps, without a
recovered candidate. Those are censored search observations, not solve times.
The current-worker searches continue after the snapshot. Prefix calibration
has five rounds per arm/curve; ranges and medians are recorded by the native
summary, not inferred as full solve durations.

Host: five exposed virtual Xeon Platinum 8573C CPUs, four-CPU quota, 16 GiB
limit, pinned CPU 4. Native ecbench isolation primitives recorded eviction,
actual affinity and NUMA observations. PSI and hardware counters were
unavailable and some user threads could not be moved: L0 only, no independent
host or sealed ecbench audit. Completed scalar checks are not an isolation
certificate. All known validation failures and scoped final checks are retained
in [validation](../../validation/README.md).

- [Native summary and raw records](../../runs/run-20261014T1901Z/snapshot.json)
- [Matched full-solve graph](../../figures/matched-full-solve.svg)
- [Reference repetition graph](../../figures/full-reference-rounds.svg)
- [Prefix-rate graph](../../figures/prefix-rates.svg)
- [Inspected three-page PDF](report.pdf)
- [Combined report and limits](../../REPORT.md)

No IC/rho ratio, new registered curve, priced IC pipeline or admitted gain is
introduced. Canonical IC progress/leaderboard/cover figures were checked for
applicability and remain unchanged. Performance visuals are copied to the
benchmark index. All source data are frozen and byte hashed.
