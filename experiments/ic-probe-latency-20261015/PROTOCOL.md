# IC probe latency and huge pages at n=83: frozen protocol (2026-10-15)

This protocol was frozen before any timing. `protocol.json` is the
machine-readable copy, and its SHA-256 goes into every receipt
(`runner_start_*.json`, `frozen.sha256`).

It tests stages 1–2 of crypto-autoresearcher `IDEA-20261015-b41f68`
(uncommitted proposal). Stage 0 is in
[`../ic-quotient-law-stage0-20261015/`](../ic-quotient-law-stage0-20261015/).

## Question

On one fresh GitHub `ubuntu-24.04` runner (a VM, Tier 1 instance scope):

1. Does backing B's n=83 K600 IC producer with 2 MiB transparent huge
   pages lower its ns per root-index probe on Q0 by at least 1.5×?
2. Under the same policies, does the tuned rho's ns per step move by under
   5%?
3. How does IC ns/probe compare with a pointer chase over the root table's
   byte size under the same page policy?

**The root table is 4 GiB.** `RootTable128::with_capacity(2·states)` gives
2^27 slots of 32 bytes. Read from crypto `770f6a69`, wide path of
`examples/koblitz_orbit_dlp_fast_online.rs`.

**This is a direct IC-baseline test.** If the reading is `thp_cuts_*`, the
page policy is a measured online-stage improvement of B's K600 IC on this
instance. That is engineering class under the AGENTS.md success criterion.
The setup (index build) is reported per arm beside it, and the gap to the
tuned rho on Q0 is reported on every row.

## Arms (the page policy is the only variable)

| policy | IC / rho producer | pointer chase (`pchase.c`) |
| --- | --- | --- |
| `4k` | started with `prctl(PR_SET_THP_DISABLE, 1)`, inherited across exec | `madvise(MADV_NOHUGEPAGE)` |
| `default` | nothing set: the runner's own THP mode, as in runs 38523707244, 38617911080 and 38689817618, whose `allocation.json` recorded `enabled=[always]`, `defrag=[madvise]` | no advice |
| `thp` | `GLIBC_TUNABLES=glibc.malloc.hugetlb=1`: glibc applies `madvise(MADV_HUGEPAGE)` to its mmap'd chunks, including the 4 GiB root table | `madvise(MADV_HUGEPAGE)` |
| `hugetlb` | not run on the IC | `MAP_HUGETLB` from reserved pages; not interleaved; skipped if the reservation fails |

Everything else is held fixed and reused unchanged:

* the binaries, inputs and checks;
* the reconciliation's `arm.py`;
* B's archived factor-log table, re-verified in the oracle;
* the restore and the crate `crates/r770` of
  `../koblitz-n83-reconcile-20261014/`, built with rustc 1.99.0 and
  `--locked`.

`thp_arm.py` wraps `arm.py`. After the fork it moves itself off the
execution CPU, then samples the producer's `smaps_rollup` every 0.5 s.
That sampling is the manipulation check.

## Schedule (`run_job.py`)

Every process runs alone, pinned to one exposed CPU, with isolated_bench's
Tier 1 counters recorded around it.

* **P1.** The pointer-chase sweep:
  * sizes 2 MiB, 64 MiB, 1 GiB, 4 GiB and 8 GiB;
  * policies 4k, default and thp;
  * two rounds, with the order reversed in round 2;
  * 2e7 dependent loads × 5 repetitions per process.
* **P2.** MAP_HUGETLB at every size the reservation covers: 4,200 pages
  requested. The reservation is released afterwards.
* **P3.** The IC on Q0, in four blocks with orders `[4k, default, thp]`,
  `[thp, 4k, default]`, `[default, thp, 4k]` and `[thp, default, 4k]`.
  Each 4k or thp IC process is followed by a 4 GiB pointer chase under the
  same policy: the interleaved null.
* **P4.** The tuned rho (`rho_tuned_r770`, Fold/64/DP6, seed 831000) on Q0,
  in the same block orders.

**Expected runtime.** Build 10–20 min, P1 10–20 min, P2 under 5 min,
P3 about 10 min (12 IC processes of about 35–45 s), P4 under 2 min.
The job limit is 240 min.

## Statistics and decision rule

* **The primary statistic** is `R_IC`: the geometric mean over 4 blocks of
  (ns/probe at 4k) ÷ (ns/probe at thp). Its 95% interval comes from the t
  distribution on the 4 log ratios (3 df).
* **Secondary statistics** are default/thp and 4k/default.
* **`R_rho`** is the same statistic on ns/step.

The rule is `analyse.py`, copied verbatim from `protocol.json`.

**Eligibility.** Every IC and rho row must be:

* valid and verified;
* IC: 8,845,441 probes and scalar 3141592653589793;
* rho: 12,592,070 steps.

The manipulation check must also pass:

* every thp IC process reaches AnonHugePages of at least 2 GiB, and every
  4k IC process shows 0;
* every thp pointer chase of at least 1 GiB is at least 90% huge, and every
  4k chase is 0% huge.

Otherwise the reading is `no_result`.

**IC readings:**

* `thp_cuts_ic_ns_per_probe_ge_1.5x`: R_IC ≥ 1.5 and the lower bound > 1;
* `thp_cuts_ic_ns_per_probe_below_1.5x`: the lower bound > 1;
* `thp_change_under_10pct`: the interval lies inside [0.9, 1.1]. This is
  the idea's own falsification condition: the TLB mechanism is wrong;
* `thp_slows_ic`: the upper bound < 1;
* `not_separated`: otherwise.

**Rho readings:**

* `rho_change_under_5pct`: the interval lies inside [0.95, 1.05];
* `rho_changed`;
* `not_resolved`.

**The idea's prediction 4 is met** if the IC reading is
`thp_cuts_ic_ns_per_probe_ge_1.5x` and the rho reading is
`rho_change_under_5pct`.

## Power and runtime

* **Interval width.** With 4 blocks and t = 3.182, a block-to-block
  log-ratio SD of 0.03 gives a half-width of about 5%. That separates 1.5×
  and 1.1× easily, and it is tight enough to read a 5% band on rho.
* **Timing noise.** In the reconciliation, the same producer on Q0 varied
  0.9% in its A/A, which is below that width.
* **Not a detector of small effects.** A pointer-chase or IC change under
  about 10% stays `not_separated`, and is reported as such.

## Controls

* **Positive control on the instrument.** The thp pointer chase must
  actually be backed by huge pages (the manipulation check). The local
  smoke showed THP lowering ns/access at 512 MiB (`smoke/`).
* **Compute control.** The tuned rho, whose working set is small.
* **Work identity.** Identical probe and step counts in every arm.
* **Interleaved null.** Each 4k and thp IC process is followed by a
  pointer chase of the table's bytes under the same policy.

## What does not count

* Changing blocks, sizes, policies or thresholds after seeing a timing.
* Pooling with any other host.
* Any local timing; `smoke/` is a harness check with stub producers.
* Reading a pointer-chase ratio as an IC speedup.

## Local validation (`smoke/`, not evidence)

The harness check ran in a shared container: `run_job.py --smoke`, with
sizes of 2 MiB, 64 MiB and 512 MiB.

* **Producers were stubs.** `smoke/stub_producer.py` replays the archived
  Q0 records of runs 38689817618 and 38617911080 and holds 600 MB of
  memory, so the wrapper, the page sampler, the parsing and the rule could
  run end to end without the n=83 build. No local n=83 build exists: the
  disk is shared and an n=83 build was not allowed here.
* **Results:**
  * THP-backed bytes were 600 MB under thp and 0 under 4k and default.
  * The rule correctly flagged the stub's 600 MB as below the 2 GiB
    threshold.
  * Every pointer chase was valid.
  * hugetlb was skipped, because no pages were reserved.
