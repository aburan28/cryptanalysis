# Fresh N83 target for the minimum-capacity known-log base

A new public point on `EC1N83Ckb1h876c2921cb64` is frozen as workload
`1bd8900e972e` for the **23,859-orbit, 3,960,594-point** known-log base.
The exact M32 table plus eighty disjoint R29 query ranges fit its
47,245,925,826-rank pair domain with **1,285,570** ranks to spare. Independent
Sage replay checked the target against the subgroup generator and verified
the entire disjoint schedule before a native stage ran.

The first native M20/R18 smoke attempt retained a `native_failure` because
its candidate spill directory was unset. After fixing that launch input,
two source-bound attempts completed on the frozen public point with identical
discrete outcomes: **29,337 Bloom positives, 29,337 exact replay misses, zero
exact hits**, and 3,960,594 actual base points. The first completed run used
164,085,760 bytes peak RSS. Its local 1.719 s subprocess wall interval is
an exploratory stage diagnostic. The second completion checks stability of
the exact result after adding the Linux full-shape launch path.

## Workload and execution boundary

The [target fixture](target_fixture.json) was generated once from a uniform
scalar in `[1,r-1]` before any native stage run. Its public point is the only
target value sent to the native producer; the fixture scalar is used by the
independent [checked Sage replay](independent_sage_target_check.json) and is
outside native computation and timing. [prepare.py](prepare.py) refuses to
replace the frozen input. The [protocol](protocol.json) binds the exact base
file, target, table and query offsets, 15-bit/10-hash Bloom filter, four
workers, and 8 GiB process cap. It retains a proposal ID and `candidate_id:
null` while the full method and one-target timing are unfinished.

The native runner [run_smoke.py](run_smoke.py) compiles the pinned portable
pair-claw source and records generated source and binary hashes. On macOS or
Linux, run a fresh M20/R18 smoke attempt with `--attempt N`; an existing
attempt is never overwritten. On Linux, `--full-shape` selects one M32/R29
wave and applies an 8 GiB `RLIMIT_AS` to the native child. That limit bounds
virtual address space and may reject allocations before RSS reaches 8 GiB;
the resulting status and stderr must be retained. A full-shape run also needs
an external wall timeout, host/allocation receipt, and process memory record
for a qualified Tier 1 or Tier 0 timing comparison. One wave is a memory and
yield gate; the complete one-target online interval must include every
target-dependent wave, failure, and recovery check, and be paired with rho
on this same public point.

## Reproduction

From the repository root, with the checked Sage launcher for verification:

```sh
python3 experiments/koblitz-pair-claw-20260929/n83_fresh_m32_k23859_20261012/prepare.py  # fresh directory only
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/koblitz-pair-claw-20260929/n83_fresh_m32_k23859_20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/koblitz-pair-claw-20260929/n83_fresh_m32_k23859_20261012/verify_sage.py
python3 experiments/koblitz-pair-claw-20260929/n83_fresh_m32_k23859_20261012/run_smoke.py --attempt 1
python3 experiments/koblitz-pair-claw-20260929/n83_fresh_m32_k23859_20261012/verify_smoke.py
```

The `prepare.py` invocation creates a **new** random point and workload ID;
reproduce this published workload by using its checked-in fixture and
protocol directly. [verify_smoke.py](verify_smoke.py) checks the preserved
failed attempt, two complete smoke receipts, exact replay counts, hashes,
base size, and pair-rank capacity. For the frozen point on a suitable Linux
instance, use `run_smoke.py --full-shape --attempt 1` after checking available
disk and the instance's memory limit. Preserve the output even when the
native process times out or fails its bounded allocation.
