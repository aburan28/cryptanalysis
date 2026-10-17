---
title: "Stacked n = 83 K600 producer: probe pipeline + 16-byte slots + state fold + rank stage, end-to-end cold"
date: 2026-10-16
---

# Stacked n = 83 K600 producer: probe pipeline + 16-byte slots + state fold + rank stage, end-to-end cold

**Status (2026-10-16): measured; frozen primary rule applied; verdict
`improvement`.** GitHub Actions run
[38862448935](https://github.com/aburan28/cryptanalysis/actions/runs/38862448935)
(attempt 1, one `ubuntu-24.04` runner, Tier 1 instance scope) ran the frozen
[protocol](protocol.json) and [schedule](schedule.json), committed before any
Tier 1 timing. Its artifact `n83-stacked-38862448935-1` is archived in
[`run_github_38862448935/`](run_github_38862448935/). On 20 new points and two
rank blocks the stack lowers the **end-to-end cold** cost (rank stage + setup +
one-target online) by **3.2391 [2.9809, 3.5240]** (E2E(kP, cP) / E2E(kS, cS)),
**in wall time on one host class** (one GitHub runner, AMD EPYC 9V74, one
pinned CPU, CPU-only), with factor-base construction charged to neither arm.
Beside it, the host-independent operation counts: the stack's rank stage
makes **1.4773x fewer probes and root calls**; the rest of its 3.3737x
rank-stage gain is 2.2837x lower wall time per probe on this host (per-probe
wall time, not host speed: a kP probe and a kS probe are not the same work). See
[Result](#result) and [Disclosures](#disclosures-2026-10-16). The numbers under "Local validation" and in
[`smoke/`](smoke/README.md) are diagnostics from the cloud-agent VM, not
timing evidence.

## Question

Main has five promoted n = 83 a = 1 K600 one-target IC improvements, each
measured on its own parent and none end to end:

| step | experiment | promoted on |
| --- | --- | --- |
| lift_scan canonicalizer | `koblitz-n83-liftscan-20261015` (#926) | online, over B |
| Feistel scan order | `koblitz-n83-scanorder-20261015` (#927) | online, over B |
| both combined | `koblitz-n83-combined-20261015` (#929) | not promoted (`not_separated` on geomeans) |
| prefetched probes (pP) | `koblitz-n83-probepipe-20261015` (#931) | online 1.40x over the combined producer |
| two-level root table | `koblitz-n83-tablefilter-20261015` (#934) | online 1.063x over pP, almost all from the 16-byte slot (pK 1.058x) |
| folded S3 root index | `koblitz-n83-state-fold-20261015` (#933) | cold (setup + online) 1.84x over the combined producer; online about 5% slower; its rank stage on lift + Feistel was 2.25x cheaper per attempt (secondary) |

None of them moved the n = 83 row of `docs/ic/BASELINES.md`, because none
measured an end-to-end cold `S` (setup + index build + rank stage + online),
and the rank stage (B's: about 750 s on the runner) dominates that cost.

Does the stack of all of them, with the rank stage run on the stack's own
probe loop, lower the **end-to-end cold** cost of the current best producer
(pP, whose rank stage is B's) on new targets, with every relation, scalar
and factor-log table unchanged? That is an iteration under AGENTS.md
"Success criterion"; a promoted result is the first n = 83 row with a
measured end-to-end cold `S` after B.

![Design (from the frozen protocol; not a result). Source:
[figures/design.tex](figures/design.tex), vector:
[figures/design.pdf](figures/design.pdf).](figures/design.png)

## What is stacked

`make_online_source.py` derives the producer in two steps:

1. `make_tablefilter_source.py` is `koblitz-n83-tablefilter-20261015`'s
   `make_online_source.py`, verbatim (with its two verbatim parents,
   `make_probepipe_source.py` and `make_combined_source.py`). Its output
   must hash to that protocol's frozen producer digest (`70233510...`). With
   `KIC_ROOT_TABLE=base` and `KIC_PROBE_PIPELINE=prefetch` it is the
   probe-pipeline producer pP; with `KIC_ROOT_TABLE=compact` it runs the
   16-byte slots.
2. Counted, exact replacements port the state fold (`koblitz-n83-state-fold-20261015`,
   `FOLD_CODE` and `fold_edits`) onto every root-table layout and probe loop:
   - `KIC_STATE_FOLD=1` stores 14,940,300 representatives of the
     29,880,000 ordered states, fills **the selected table** (32-byte or
     16-byte slots, or the filter's compact table) from them in the
     baseline's insertion order (capacity follows the stored count, 2^26
     slots), and the folded scan now calls the layout's own probe loop
     (`scan_state128_select::<C, P>`) for each class at its first
     occurrence in the baseline order; mates are rebuilt by two rotations.
     `KIC_FOLD_PLANT` and `KIC_INDEX_CANON` keep the state fold's semantics.
   - **The rank stage** gets `KIC_RANK_CANON` and `KIC_RANK_ORDER` (as in the
     state fold) and the new `KIC_RANK_PROBE=target`, which runs the
     arm's own probe loop in the rank stage: the prefetch pipeline on the
     32-byte table, or the compact (or filter) loop on the 16-byte table.
     So the stack's rank stage runs on the 16-byte table in the same
     process; the parent's rule that a non-base layout needs the cached
     factor-log table now applies only to `KIC_RANK_PROBE=off`. Each rank
     process records every attempt's probes and ns and
     `rank_relations_blake3`, a digest of every attempt's relation.
   - `KIC_INDEX_DIGEST=1` writes the state fold's index digests (logical
     states in index order; the table's key -> value map), read from
     whichever table the index holds, after the target and outside every
     interval.

**Exactness argument.** Each part is exact on its own (its parent's tests
and gates): the 16-byte slot stores the same key -> value map and the same
probe sequence; the pipeline keeps probe order and early return; the fold
finds the baseline's first relation with fewer probes (the skipped mates
made the same probes without a hit). The port changes only which loop the
folded scan calls, and every loop takes a `State128`, so a folded scan over
the compact table makes the compact loop's probes on the baseline's logical
order. In the rank stage, the attempts are a deterministic function of the
rank seed and the earlier relations; if every attempt's relation is
unchanged, the rank stage's echelon, attempts and factor-log table are
unchanged. The tests and the smoke below check all of this.

**Left out, and why.**

- **The root filter** (`KIC_ROOT_TABLE=filter`) is not in the stack: on the
  runner it added 1.005x on top of the 16-byte slot (run 38829449594). It is a
  secondary arm (`cSF`), cold only.
- **lift_scan in the index build** (`KIC_INDEX_CANON=lift`, the state fold's
  cF/cFI 1.33x cold secondary) was never promoted. It is a secondary arm
  (`cSI`), cold only; the time budget did not allow its own rank arm, and its
  rank stage is the stack's (it changes only the build).

## Frozen Tier 1 design

One GitHub `ubuntu-24.04` runner, one pinned CPU, Tier 1 counters, one fresh
process per run. Every IC arm runs lift_scan, the Feistel order and the
prefetch pipeline on the online path.

| Arm | Table | Fold | Rank stage | Role |
| --- | --- | --- | --- | --- |
| `cP` / `kP` | 32-byte | no | B's: full scan, left-major, sequential probes | **baseline** pP |
| `cS` / `kS` | 16-byte | yes | lift, Feistel, the stack's compact loop | **candidate**: the stack |
| `cSaa` / `kSaa` | 16-byte | yes | as kS | A/A |
| `cSX` | 16-byte | yes + planted | (cold only) | planted positive control: the fold's removed work, redone and discarded |
| `cSmF` / `kSmF` | 16-byte | no | lift, Feistel, compact loop | ablation: stack minus fold |
| `cSmS` / `kSmS` | 32-byte | yes | lift, Feistel, prefetch pipeline | ablation: stack minus slots |
| `cSF` | filter + 16-byte | yes | (cold only) | optional component: 32 MiB filter |
| `cSI` | 16-byte | yes, lift in build | (cold only) | optional component: lift_scan index build |
| `rT` | — | — | — | tuned rho rT770 (Fold/64/DP6), seed 870000 + point seed |

- **Cold panel.** 20 new public points (`inputs/cold_targets.json`, role
  `stacked-cold-v1`, `make_targets.py`), checked disjoint from Q0, B's panel
  and every earlier n = 83 panel of the law on main (scan-order held-out 384,
  combined 576, probe-pipeline 384, state-fold 16, table-filter 384), all
  regenerated. No scalar is known for any of them. Each `C<i>` segment runs
  one process per cold arm on point s(i-1), shuffled.
- **Rank blocks.** `K1`, `K2` (rank seeds 101, 102): one process per rank
  arm, each: setup, the rank stage to full rank, linear algebra, then one
  target (s000, s001). Every written factor-log table must equal B's
  archived table, log for log.
- **Q0 block** `O1`: cP and cS on Q0, exactness against the archived
  Feistel identity.
- **Segment order:** O1, C1-C4, K1, C5-C12, K2, C13-C20; 300-minute guard.

**Primary (pre-registered): the end-to-end cold ratio.**
E2E(k, c) = mean rank stage of rank arm k over its two processes + mean cold
(setup + one-target online, cached table) of cold arm c over the 20 points.
R = E2E(kP, cP) / E2E(kS, cS); bootstrap: points resampled (paired), and the
attempts of each rank process resampled (its non-attempt time kept), 10,000
draws. **Improvement** iff the 95% lower bound of R exceeds 1; regression iff
the upper bound is below 1; otherwise not separated. **Invalid** if any
gate or control fails or any scheduled row is missing.

**Online is co-reported, never decides**: online cP/cS (means and geomeans),
and the fold's online cost inside the stack (online cSmF/cS).

- **Controls.** A/A: E2E(kS, cS)/E2E(kSaa, cSaa) and cold cS/cSaa both inside
  [0.97, 1.03]. Planted: cold cSX/cS lower bound above 1.
- **Gates.** Every IC process: its layout, slot count (2^27 unfolded, 2^26
  folded), 29,880,000 logical states, 14,940,300 stored iff folded,
  29,878,182 table entries, and B's index digests. Per point: one scalar
  across every IC process and rT (oracle replay); one relation across every
  IC process; probes cP = cSmF; cS = cSaa = cSX = cSmS = cSF = cSI ≤ cP;
  cSX + audit = cP. Rank: B's table; per block, one relation digest across
  kS, kSaa, kSmF, kSmS; identical per-attempt probes across kS, kSaa, kSmS;
  kSmF ≥ kS per attempt. Q0: archived relation and scalar, probes 1,988,184
  (cP) and 1,987,852 (cS).
- **Secondaries.** Online, cold-without-rank, setup, index and peak-RSS
  ratios cP/cS; ablations E2E(kSmF, cSmF)/E2E(kS, cS) and
  E2E(kSmS, cSmS)/E2E(kS, cS) with their online, cold and setup ratios; cS
  over cSF and cSI; rank-stage and per-attempt ratios kP/kS, kSmF/kS,
  kSmS/kS; each rank process's single-process end-to-end cold time; `S` =
  cost / (rT ms/step) / sqrt(r) for end-to-end cold, cold without rank and
  online, per arm; delta `S` cP to cS; the end-to-end cold gap IC / rT and
  the online gap to rT (distance remaining, not a gate).
- **Power** (`power_check.py`, `analysis/power.json`; prior
  `inputs/power_prior.json` built by `make_power_prior.py` from the state
  fold's run 38819494806 and three measured factors). The rank stage, not
  the point count, limits resolution. At the minimal effect of interest,
  1.15, the power is 0.88-0.93 at every size from 4 to 20 points (300
  simulations; the smallest size passing 0.80 after two Monte Carlo SEs is
  4); at 1.10 it is 0.55-0.63, so end-to-end effects of 10% or less are not
  reliably resolved by this design. The prior's expected ratio is 3.2 (pP
  rank stage about 757 s, cold about 42 s; stack about 228 s and 22 s).
  20 points serve the per-point online ablations (power to see the fold's
  5% online cost inside the stack: 0.98 at 8 points, 1.0 at 16-20).
- **Runtime estimate.** About 3 h including the build (up to about 3.5 h on
  a slower runner); 300-minute time guard, 350-minute job limit.

## Local validation (cloud-agent VM; diagnostics, no timing claims)

See [`smoke/README.md`](smoke/README.md).

## Result

All gates pass: every scheduled row is present and valid (192 valid, 0
invalid, 0 skipped by the time guard; 20/20 points complete), probe
identities, one relation per point across every IC process, one scalar per
point across every IC process and the tuned rho (replayed in the pinned
oracle), Q0 equal to the archived Feistel identity, every rank process's
factor-log table equal to B's archived table, and identical rank relations and
per-attempt probes across layouts. Both controls pass.
`verify_receipt.py` re-run on the archive reproduces `panel/result.json`,
`panel/result_table.md` and `verify-stdout.json` byte for byte. The verifier
flags one contention note on two rows: major page faults on serial 2 (`cS`)
and serial 12 (`cSaa`); both rows are valid and stay in.

![Frozen ratios with 95% bootstrap intervals, all from `result.json`
([source](figures/result.tex), [vector](figures/result.pdf), rendered by
[`make_figures.py`](make_figures.py)).](figures/result.png)

### Primary (frozen rule)

Improvement iff the 95% lower bound of R = E2E(kP, cP) / E2E(kS, cS) exceeds 1.

| Statistic | Estimate [95%] | Reading |
| --- | --- | --- |
| **R = E2E cP / cS** (20 points, 2 + 2 rank processes) | **3.2391 [2.9809, 3.5240]** | **improvement** |
| A/A E2E cS / cSaa | 0.9996 [0.9339, 1.0697] | pass (inside [0.97, 1.03]) |
| A/A cold cS / cSaa | 0.9986 [0.9970, 0.9999] | pass (inside [0.97, 1.03]) |
| planted cold cSX / cS | 1.7351 [1.7293, 1.7404] | pass (lower bound above 1) |

End-to-end cold means (rank stage mean over two processes + mean cold over 20
points): cP 869.8 + 49.4 = 919.2 s; cS 257.8 + 26.0 = 283.8 s. Single-process
end-to-end cold ratio kP / kS 3.2397.

### Secondaries (none changes the verdict)

| Quantity | cP (baseline) | cS (stack) | Ratio cP / cS [95%] |
| --- | ---: | ---: | :--- |
| cold without rank stage (ms) | 49,372.8 | 25,960.4 | 1.9019 [1.8937, 1.9096] |
| setup (ms) | 49,004.5 | 25,575.2 | 1.9161 [1.9112, 1.9211] |
| index build (ms) | 46,404.8 | 22,991.2 | 2.0184 [2.0132, 2.0240] |
| online (ms) | 368.3 | 385.1 | 0.9562 [0.9524, 0.9608] (geomeans 0.9580 [0.9533, 0.9622]) |
| peak RSS (MiB) | 5,544.6 | 1,788.4 | 3.1004 [3.1001, 3.1006] |
| rank stage, mean per process (s) | 869.8 | 257.8 | 3.3737 |
| rank per attempt (ms; probes) | 1,449.4; 2,480,245 | 429.5; 1,678,903 | 3.3749 [3.0914, 3.6806] |

- **Online is not faster; it is about 4.6% slower** in the stack (cS online
  385.1 ms against 368.3 ms). The ablations below place the cost in the fold
  (about 6.4% online); the 16-byte slots give back about 2.3%. The gain is in
  the rank stage and setup.
- **Ablations (the stack minus one part; mean per-arm numbers).**

  | Ablation | E2E ratio [95%] | online | cold without rank | setup | rank per attempt |
  | --- | --- | --- | --- | --- | --- |
  | stack minus fold (`cSmF`, `kSmF`) / stack | 1.0272 [0.9622, 1.0971] | 0.9394 [0.9363, 0.9420] (geomean 0.9396) | 1.8662 [1.8594, 1.8722] | 1.8802 [1.8782, 1.8820] | 0.9427 [0.8740, 1.0207] |
  | stack minus slots (`cSmS`, `kSmS`) / stack | 1.0231 [0.9543, 1.0958] | 1.0228 [1.0195, 1.0249] (geomean 1.0217) | 1.0106 [1.0090, 1.0120] | 1.0104 [1.0088, 1.0118] | 1.0244 [0.9489, 1.1043] |

  End to end, neither ablation is separated from 1 (both intervals contain
  1): the attempt-level rank-stage intervals are wide, and the rank stage
  dominates the end-to-end cost. The fold's effect shows in the setup (1.88x) and in a 6.4% online
  cost; the slots' effect shows in the 2.4% online and 1% setup gains and
  in peak RSS (the 32-byte table without slots peaks at 2,812 MiB against
  1,788 MiB; without the fold 3,497 MiB).
- **Optional components.** The 32 MiB filter (`cSF`) is slower cold without
  rank (cS / cSF 0.9673 [0.9658, 0.9687]) and 7.2% faster online (online cS /
  cSF 1.0715 [1.0684, 1.0746]); lift_scan in the index build (`cSI`) is
  1.3308 [1.3270, 1.3342] faster cold without rank, with online unchanged
  (cS / cSI 1.0013 [0.9980, 1.0047]). Neither is in the stack; `cSI` is a
  candidate next improvement to the setup.
- **S** (cost over this run's measured rT770 step, 316.66 ns, per sqrt(r)):

  | Arm | E2E cold | cold without rank | online |
  | --- | ---: | ---: | ---: |
  | cP | 31.356 | 1.6843 | 0.012562 |
  | cS | 9.680 | 0.8856 | 0.013137 |
  | cSaa | 9.684 | 0.8869 | 0.013115 |
  | cSmF | 9.944 | 1.6527 | 0.012341 |
  | cSmS | 9.904 | 0.8949 | 0.013437 |
  | cSF, cSI, cSX | not E2E | 0.9156, 0.6655, 1.5366 | 0.012260, 0.013120, 0.013120 |

  Delta S end-to-end cold cP to cS = -21.675; delta S online +0.000575. The
  tuned rho's own `S` here: cold 0.10253, online 0.09443.
- **Gap to tuned rho rT770** (IC / rho; 20 points; distance remaining, not a
  gate). End-to-end cold: cP 305.8238 [237.4977, 403.7772], cS 94.4168
  [73.5188, 125.2922]. Online: tuned rho / cP 7.5168 [4.4063, 13.5984],
  tuned rho / cS 7.1879 [4.1981, 12.9440] (IC / rho 0.1391 [0.0773, 0.2368]
  for cS). Mean rT770 cold 3,005.6 ms, online 2,768.1 ms.
- **Rank stage.** Per-attempt cost: kP / kS 3.3749 [3.0914, 3.6806]; kS / kSaa
  0.9997 [0.9266, 1.0741]; kSmF / kS 0.9427 [0.8740, 1.0207]; kSmS / kS 1.0244
  [0.9489, 1.1043]. Whole-stage ratios kP / kS 3.3737, kSmF / kS 0.9427,
  kSmS / kS 1.0244. Mean attempt probes: kP 2,480,245; kS, kSaa, kSmS
  1,678,903; kSmF 1,679,182 (the unfolded scan's probes).
  After the stack the rank stage is still 91% of the end-to-end cold cost
  (257.8 of 283.8 s).

### Limits of this result

- Tier 1, instance scope: one runner (`runnervm8k3b6`), one pinned CPU,
  20 cold points, two rank processes per rank arm, one fresh process per arm
  per point. The primary's interval is over the points and the rank attempts
  of those two processes (the rank blocks were not repeated more often).
- The power analysis resolves effects of about 15% and larger end to end;
  the ablations (about 2-3%) are not separated end to end, and the sign of
  the rank-stage ablation effects is within noise. They are secondaries.
- The stack is a combination of five promoted steps, each on its own parent.
  The primary compares it with pP, which has B's rank stage; the 3.24x is
  the combined gain of the fold, the 16-byte slots and the rank-stage change
  (lift_scan, Feistel and the stack's probe loop on the rank stage), not of
  one part.
- The end-to-end cold figure is the first measured n = 83 cold `S` after B's
  baseline (32.93 in B's run, a different run, instance set and step time).
  The gap to the tuned rho is still about 94x.

### Disclosures (2026-10-16)

Added after sheriff case SHF-20261016-3caa6f (crypto-autoresearcher
`research/sheriff/SHF-20261016-3caa6f/`, findings K1, K2 and R1, all minor).
No measurement, statistic or verdict above changes; the numbers below are
recomputed from [`panel/result.json`](run_github_38862448935/panel/result.json)
and the rank records in `panel/runs/` (00042, 00043, 00116, 00120).

- **Wall time, not operation counts (K1).** R = 3.2391 and every `S` in this
  report are wall time from one run on one host class, converted to this
  run's rT770 step. The host-independent part is the rank stage's operation
  count:

  | Rank stage, both processes (1,200 attempts per arm) | kP (pP) | kS (stack) | kP / kS |
  | --- | ---: | ---: | ---: |
  | probes | 2,976,293,514 | 2,014,683,345 | 1.4773 |
  | root calls | 1,488,248,100 | 1,007,441,716 | 1.4773 |
  | wall time (ms) | 1,739,592.6 | 515,628.5 | 3.3737 |
  | wall ns per probe | 584.48 | 255.94 | 2.2837 |

  3.3737 = 1.4773 x 2.2837: fewer probes (the Feistel order; deterministic in
  the rank seed) times lower per-probe wall time on this host. The 2.2837 is
  per-probe wall time, not a host-speed factor: a kP probe (full
  canonicalization, base table, sequential loop) and a kS probe (lift_scan,
  compact table, prefetch loop) are not the same work, so it mixes cheaper
  per-probe work with host and memory-system effects. It cannot be split
  into the two until field operations per probe are emitted (follow-up 1). Stored index
  states halve (29,880,000 to 14,940,300; build time 2.0184x); online probes
  are equal (cP / cS 1.000133 over the 20 points). Setup and index build emit
  no count comparable to probes, so no single end-to-end operation-count
  ratio exists; the rank stage is 94.6% (pP) and 90.9% (stack) of the
  end-to-end wall time. The improvement holds on every emitted counter; its
  magnitude on another host needs that host's per-probe wall time.
- **Uncharged phase (K2).** Factor-base construction is charged to neither
  arm: every IC process loads the K600 base (99,600 points) from
  `base_n83_K600.jsonl` (`base_source` `retained_header`; the about 0.31 s
  `base_load` is parsing only). AGENTS.md puts `T_factor_base` in `T_cold`
  and makes a missing phase unknown, not zero. The phase is common to both
  arms, so R > 1 for any construction cost X >= 0, but R falls and the cold
  `S` rises with X: X = 1 s gives R 3.2312 and `S` 9.7146; 10 s, 3.1629 and
  10.0216; 60 s, 2.8483 and 11.7272. So 3.2391 bounds the every-phase ratio
  from above and `S` 9.6805 bounds the every-phase cold `S` from below. B's
  README (`koblitz-n83-bl-arm-20261014`) disclosed the same exclusion.
- **No §5a band (K2).** The 0 / 0.1 / 1 GAE band for the IC / rho gap
  cannot be computed from this run: the IC arms emit rank-stage probes and
  root calls, online probes and stored states, but no group additions,
  scalar multiplications, canonicalizations, fold rotations or index
  inserts. The gap 94.4 [73.5, 125.3] holds as a wall-time figure on this
  host only. Between the two IC arms the order holds on every emitted
  counter.
- **No other-host replay (R1).** The run was not replayed on another host
  class. Preregistration is provable from GitHub records (protocol commit
  `24abca74` is the parent of the result commit on `claude/n83-stacked`),
  not from main's squashed history.

### Follow-up (proposed, not run; the frozen code here is not changed)

1. **Counted group operations.** A new experiment whose producer emits, per
   phase, group additions, scalar multiplications, canonicalizations (full
   and lift), fold mate-rebuild rotations and index inserts beside probes
   and root calls, so the §5a band can be reported for the IC / rho gap.
   It needs a change to the producer source (`make_online_source.py` and its
   derivation chain), which would change this protocol's frozen producer
   digest, so it belongs in a new protocol, not here.
2. **Cross-host replay of rank block K1.** kP and kS, rank seed 101, in the
   order kS, kP, kP, kS, on another host class, with one timed cold
   construction of the K600 base in the same job. Check: per-attempt probe
   counts equal the archived ones exactly; the per-probe ratio (2.2837 here)
   on the second host; the construction time X. R < 2 would need the
   per-probe ratio to fall to 1.358 (holding kP's per-probe wall time and
   both cold arms at this run's values; 1.361 if kS's is held instead). The frozen schedule and producer
   have no attempt cap, so the replay runs K1 to full rank (600 attempts;
   about 40 minutes for the four processes on this runner) and the first 100
   attempts are read from the per-attempt records. Preregistered on
   2026-10-17 as `../koblitz-n83-replay-20261017/PROTOCOL.md` (workflow
   `n83-replay.yml`); result pending, and nothing in this report changes
   until it is archived.

## Files

| File | Role |
| --- | --- |
| `protocol.json`, `make_protocol.py`, `schedule.json`, `make_schedule.py` | frozen protocol, its builder, frozen run order |
| `make_online_source.py`, `make_tablefilter_source.py`, `make_probepipe_source.py`, `make_combined_source.py`, `online/`, `lift2/` | the stacked producer (verbatim parent derivations, digest-checked, plus the fold port and rank selectors); tuned rho; the two-limb canonicalizer crate |
| `restore.py`, `check_log_table.py` | restore and digest-check crypto 770f6a69 and every local source; re-verify B's factor-log table |
| `make_targets.py`, `inputs/cold_targets.json` | the new cold panel |
| `inputs/archived_identities.json` | archived Q0 identity (from `koblitz-n83-tablefilter-20261015`) |
| `make_power_prior.py`, `inputs/power_prior.json`, `power_check.py`, `analysis/power.json` | power prior, simulation, result |
| `arm.py`, `run_schedule.py` | one arm per pinned process; the schedule runner |
| `verify_receipt.py` | gates, statistics, decision rule; `result.json`, `result_table.md` |
| `figures/design.*` | design diagram (TikZ source, PDF, PNG) |
| `smoke/` | local diagnostics |
| `run_github_38862448935/` | the archived artifact: allocation, builds, raw runs, `panel/result.json` |
| `make_figures.py`, `figures/result.*` | result figure (TikZ source, PDF, PNG) |
| `README.pdf` | this report: `pandoc README.md -o README.pdf --pdf-engine=pdflatex -H report_header.tex --lua-filter report_filter.lua -V geometry:margin=2cm -V fontsize=10pt -V colorlinks=true` |
