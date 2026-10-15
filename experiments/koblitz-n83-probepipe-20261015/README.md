---
title: "Probe pipeline: prefetched root-table probes for the combined n = 83 K600 one-target index calculus"
date: 2026-10-15
---

# Probe pipeline: prefetched root-table probes for the combined n = 83 K600 one-target index calculus

**Status (2026-10-15): profile done (diagnostic), fix implemented and
checked for exactness, protocol frozen, Tier 1 run started; no result yet.**
The frozen [protocol](protocol.json) and [schedule](schedule.json) were
committed before any Tier 1 timing. The run is the push-triggered workflow
`.github/workflows/n83-probe-pipeline.yml` on branch
`claude/n83-probe-pipeline`. Its receipt, result, result figure and the
refreshed PDF are owed after the run. Nothing on this page is a Tier 1
measurement yet.

## Question

The n = 83 a = 1 K600 one-target IC's online interval is about 100%
`target_PDP`: per probe, a batched S3 root solve, a `to_normal` byte-table
conversion, canonicalization, and a lookup into the ~4 GiB root table. Two
promoted improvements are now combined (`claude/n83-combined`, protocol
frozen, run 38803625711 in flight): `lift_scan` canonicalization (1.52x
online) and the Feistel scan order (1.45x on held-out points). The
`ic-probe-latency-20261015` experiment measured an IC probe at 574 ns against
a bare 4 GiB pointer chase at 140 ns.

Which component dominates the combined producer's probe, and does the fix
that matches it lower the one-target online time on new public points, with
probes, relation and scalar unchanged? Under AGENTS.md's success criterion,
a verified, measured improvement over the current baseline is a success and
becomes the new baseline.

## 1. Profile of the combined probe path (diagnostic)

All numbers in this section come from the cloud-agent VM, a shared 4-vCPU
guest. They chose the fix; they are not evidence of a speedup. The raw files
are in [`smoke/profile/`](smoke/profile/), the table in
[`analysis/profile_local.json`](analysis/profile_local.json)
(`analysis/make_profile_table.py`).

- **Instrument.** The profiler `ic_probe_profile_r770`
  (`make_profile_source.py`, a derived copy of the producer that is never a
  timed arm) walks the first 400 index states of target w11's Feistel order
  (132,800 probes) and times cumulative variants of the per-state work, all
  probes and no early exit, 7 rounds in rotated order: roots; + `to_normal`;
  + `lift_scan`; + inline lookup (the combined loop); and, for comparison,
  the pipelined lookup. Differences are marginal costs in situ. The root
  table is THP-backed (`glibc.malloc.hugetlb=1`), as on the runner, whose
  THP mode is `always`.
- **Instruction counts.** callgrind on the same profiler, one variant per
  run, with 1 and 2 passes; the difference is one pass, so setup cancels.
  It runs on a constructed K = 40 base (200 states, 66,400 probes), because
  instructions per probe do not depend on the table size
  ([`smoke/profile/callgrind.sh`](smoke/profile/callgrind.sh)).
- **The rest.** The real producer (`KIC_PROBE_PIPELINE=off`, the combined
  loop) on w11, w08 and w14 ran at 472 ns/probe on the same VM. That is the
  inline-lookup variant's 474 ns within noise, so everything else (hits,
  lift, relation check, laps, the Feistel order) is about 0.

| component | ns/probe (diagnostic) | share of 472 ns | instructions/probe (callgrind) |
| --- | ---: | ---: | ---: |
| root solve (2n inputs + batched S3 solve) | 130 | 28% | 132 |
| `to_normal` conversion | 16 | 3% | 187 |
| `lift_scan` canonicalization | 52 | 11% | 334 |
| **root-table lookup (4 GiB)** | **276** | **59%** | **22** |
| rest | about 0 (-2) | 0% | |

**The dominant cost is the root-table lookup, and it is latency-bound:**
22 instructions per probe take 276 ns, 59% of the probe. The compute
components together are 198 ns. Instruction counts per variant come from a
different codegen of each variant, so the per-component instruction split
(especially conversion against root solve) is approximate; the
latency reading does not depend on it.

![Probe-path profile (diagnostic)](figures/probe_profile.png)

So the fix is the latency fix, not a wider batch for the root solve (28%) or
a GFNI/clmul conversion (3%).

## 2. The fix: software-pipelined probes with prefetch

`make_online_source.py` derives the producer in two steps:

1. `make_combined_source.py` is `claude/n83-combined`'s
   `make_online_source.py` @ 88e1929fb, verbatim. Its output must hash to
   the combined protocol's frozen producer digest (`f65e518a...`), so the
   baseline text is exactly the combined producer.
2. Counted, exact replacements add a compile-time selector `P` on the
   target scan, chosen per process by `KIC_PROBE_PIPELINE`:
   - `off`: `scan_state128`, byte for byte unchanged (the combined loop);
   - `prefetch`: `scan_state128_pipelined`. Same root batch. Then, in the
     same candidate order (shift outer, stored root inner, solver partner
     order), every partner's `to_normal` word and `lift_scan` key, each
     followed by `_mm_prefetch(T0)` of its home slot. Then the lookups, lift
     and relation check in that same order, with the same probe counter
     and the same first-hit return.

**Exactness.** The probe sequence, the counter, the lookup, the lift and the
return are those of `off`, so the probes, relation and scalar are identical
on every target. The only extra work is computing keys for the probes after
the successful one in the final state (at most 4n - 1 canonicalizations),
which the clock charges. The rank stage always runs `PIPE_OFF`. Locally, on
w11, w08 and w14, both settings gave identical probes (160,866, 161,864,
183,505), relations and scalars, equal to the earlier combined binary's; see
[`smoke/`](smoke/README.md).

![The two loop structures](figures/probe_pipeline.png)

In the profiler the pipelined lookup costs 145 ns/probe instead of 276
(474 → 343 ns/probe, diagnostic). A deeper, cross-state pipeline (a state's
lookups consumed after the next state's keys) gave the same 342 ns, so the
remaining lookup cost is not a short prefetch distance. The lookup-only
loops (65-73 ns per lookup with no compute) point at TLB and page-walk cost
under the VM's nested paging; that is a hypothesis for the next step, not a
measurement.

## 3. Frozen Tier 1 design

| Arm | Canonicalizer | Order | Probe loop | Panel | Role |
| --- | --- | --- | --- | --- | --- |
| `pC` | lift | Feistel | off | primary | baseline: the combined producer |
| `pP` | lift | Feistel | prefetch | primary | candidate |
| `pPaa` | lift | Feistel | prefetch | primary | A/A control |
| `pX` | lift + discarded full scan | Feistel | prefetch | primary | planted positive control |
| `rT` | — | — | — | primary, every point | tuned rho rT770 (Fold/64/DP6), seed 850000 + point seed |
| `oC`, `oP` | lift | Feistel | off / prefetch | Q0 + B's 16 fresh, 1 block | exactness against the archived Feistel identities; secondary |

- **Primary panel.** 384 new public points (`inputs/primary_targets.json`,
  `make_targets.py`) from B's public hash-to-curve law with the new role
  `probepipe-primary-v1`, seeds 0..383. They are checked disjoint from Q0,
  B's 16 fresh points (role `eval`), the 384 scan-order held-out points and
  the 576 combined primary points (both regenerated from the law). No scalar
  is known for any of them.
- **One job, one pinned CPU.** Six primary slices of 64 points and one
  Q0 + fresh block, P1, P2, P3, O1, P4, P5, P6. Within each segment the
  order is a seeded shuffle. Every primary slice holds one process per IC
  arm and one rho process per point. Each IC process does its setup once and
  then gives each target its own one-target online interval.
- **Primary statistic.** R_m = mean `pC` / mean `pP`, online time over all
  384 points, bootstrap over points, 10,000 resamples.
- **Decision rule.** **Improvement** iff the 95% lower bound of R_m exceeds
  1; regression iff its upper bound is below 1; otherwise not_separated. The
  verdict is **invalid** if an exactness gate fails, the A/A (`pP`/`pPaa`
  inside [0.97, 1.03]) or the planted control (`pX`/`pP` lower bound above
  1) fails, or any of the 384 points lacks a valid row in an arm.
- **Also reported.** R_g (paired geometric means), ns/probe per arm, the
  probe ratio (must be exactly 1), the new `S_rho` for `pC` and `pP` and its
  delta, the tuned-rho gap on the same points, the slice bootstrap and
  per-slice ratios, and the Q0 + fresh block.
- **Exactness gates.** On every primary point the four IC arms have
  identical probes and relation; one scalar across them and the tuned rho;
  every scalar replays as [d]G = Q in the pinned oracle. On Q0 + 16 fresh,
  both arms reproduce the archived Feistel probes and relations of run
  38786433493, the archived scalars, and Q0's validation sidecar.
- **Power, checked before freezing** (`power_check.py`,
  `analysis/power.json`). The population is the old held-out panel's
  measured Feistel times over the measured lift_scan ratio. The per-point
  effect spread is the 16 measured lift_scan ratios', with timing noise
  sigma 0.02 per target and 0.01 per process. For a minimal effect of
  interest of 1.03, power is 0.81 at 64 points, 0.92 at 128 and 1.00 at 384.
  The smallest size passing 0.80 after two Monte Carlo SEs is 128. The panel
  is the design floor of 384, so that the slice bootstrap has six clusters.
- **Runtime estimate.** About 1.0 to 1.6 h including the build, with a
  300-minute time guard. A last step runs the profiler on Q0 on the runner
  (`profile_diagnostic_*.json`), diagnostic only; it never enters the
  decision.

## Local validation (cloud-agent VM; no timing claims)

See [`smoke/README.md`](smoke/README.md).

## Files

| File | Role |
| --- | --- |
| `protocol.json`, `make_protocol.py`, `schedule.json`, `make_schedule.py` | frozen protocol, its builder, frozen run order |
| `make_combined_source.py`, `make_online_source.py`, `online/`, `lift2/` | combined producer (verbatim derivation, digest-checked) plus the probe-pipeline selector; tuned rho; the two-limb canonicalizer crate |
| `make_profile_source.py`, `analysis/make_profile_table.py`, `analysis/profile_local.json`, `smoke/profile/` | the diagnostic profiler, the profile table and its raw inputs |
| `restore.py`, `check_log_table.py` | restore and digest-check crypto 770f6a69 and every local source; re-verify B's factor-log table |
| `make_targets.py`, `inputs/primary_targets.json` | the new primary panel |
| `inputs/archived_identities.json` | archived probes, relations and scalars of Q0 and the 16 fresh points (from `claude/n83-combined`) |
| `power_check.py`, `inputs/power_prior.json`, `analysis/power.json` | power simulation, its prior, its result |
| `arm.py`, `panels.py`, `run_schedule.py` | one arm per pinned process; panels; the schedule runner |
| `verify_receipt.py` | gates, statistics, decision rule; `result.json`, `result_table.md` |
| `make_figures.py`, `figures/` | TikZ sources and renders of the profile and the pipeline diagram |

## Limits

- The profile is a VM diagnostic. Its component split can differ on the
  runner (an AMD EPYC in recent runs); the runner's profiler step records
  the same variants there, still as a diagnostic.
- Tier 1, instance-scoped: one runner, one pinned CPU, not host-isolated.
- `pC` is the combined producer's probe loop compiled into the same binary
  as `pP`, as a separate monomorphization. This experiment does not re-run
  the combined experiment's own binary; it compares the two loops on the
  same points in one job.
- The tuned-rho gap is distance remaining, not a claim to beat rho.
- Next step after this run: the residual lookup cost (TLB and page walks
  under nested paging, by hypothesis). Candidates are a smaller table slot
  (16 bytes instead of 32) or a two-level table whose first level stays
  cache- and TLB-resident.
