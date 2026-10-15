---
title: "lift_scan x Feistel order: the combined n = 83 K600 one-target index calculus"
date: 2026-10-15
---

# lift_scan x Feistel order: the combined n = 83 K600 one-target index calculus

**Status (2026-10-15): protocol frozen, Tier 1 run started; no result yet.**
The frozen [protocol](protocol.json) and [schedule](schedule.json) were
committed before any timing. The run is the push-triggered workflow
`.github/workflows/n83-combined.yml` on branch `claude/n83-combined`. Its
receipt, result, figures and PDF are owed after the run. Nothing on this page
is a measurement yet.

## Question

Two measured, promoted n = 83 a = 1 K600 one-target IC improvements change
different factors of the online cost:

- **lift_scan** (PR #926, `claude/n83-liftscan` @ 8f6b4057e, run
  38776966036) replaces the 83-rotation partner-root canonicalizer with the
  exact two-limb `lift_scan`. It cuts ns/probe by 1.515 [1.506, 1.525] and
  leaves the probes unchanged.
- **Feistel scan order** (PR #927, `claude/n83-scan-order` @ af41562e7, run
  38786433493) visits the same index states in a keyed pseudo-random order
  instead of left-orbit-major. It cuts probes. On its held-out 384-point
  panel the ratio of means was 1.45 [1.20, 1.74], and mean probes over the
  law fell from 1.43 to 0.97.

Each was measured against B with the other factor at baseline. Does the
combination beat the better of the two single changes on new targets? Under
AGENTS.md's success criterion (PR #919), a verified, measured improvement
over the current baseline is a success and becomes the new baseline.

## The producer

`make_online_source.py` derives the producer from B's patched producer
(crypto 770f6a69 plus B's `ic_log_cache.patch`). It applies the two parents'
counted, exact string replacements in sequence:

1. lift_scan's edits, verbatim, plus one planted canonicalizer,
   `lift_plus_full`;
2. the scan order's edits, with the old strings adapted to the text after
   step 1, so the target scan carries both `<const C: u8, const O: u8>`.

Each process picks its arm with `KIC_TARGET_CANON` (`full`, `lift`,
`lift_plus_full`) and `KIC_SCAN_ORDER` (`left_major`, `feistel`). The rank
stage always uses the full scan and left-major order. Locally, the parents'
own derivations reproduce their frozen producer digests from the same
restored input, so both merges start from the exact measured text.

## Frozen design

| Arm | Canonicalizer | Order | Panel | Role |
| --- | --- | --- | --- | --- |
| `pB` | full | left-major | primary | B |
| `pL` | lift | left-major | primary | lift_scan only |
| `pF` | full | Feistel | primary | Feistel only |
| `pLF` | lift | Feistel | primary | candidate (combined) |
| `pLFaa` | lift | Feistel | primary | A/A control |
| `pX` | lift + discarded full scan | Feistel | primary | planted positive control |
| `rT` | — | — | primary, every point | tuned rho rT770 (Fold/64/DP6), seed 840000 + point seed |
| `hB`, `hL`, `hF`, `hLF` | as above | as above | old 384 held-out | secondary |
| `oB`, `oL`, `oF`, `oLF` | as above | as above | Q0 + B's 16 fresh, 2 blocks | secondary |

- **Primary panel.** 576 new public points (`inputs/primary_targets.json`,
  `make_targets.py`). They come from B's public hash-to-curve law with the
  new role `combined-primary-v1`, seeds 0..575. They are checked disjoint
  from Q0, the 16 fresh points and the 384 old held-out points. No scalar is
  known for any of them.
- **One job, one pinned CPU.** Nine primary slices of 64 points, interleaved
  with six old held-out slices and two Q0 + fresh blocks: P1, H1, P2, H2,
  P3, O1, P4, H3, P5, H4, P6, O2, P7, H5, P8, H6, P9. Within each segment
  the order is a seeded shuffle. Every primary slice holds one process per
  IC arm and one rho process per point.
- **Process model.** Each IC process does its setup once and then gives
  each target its own one-target online interval. No target-dependent work
  is shared between targets.
- **Primary statistic.** The better single arm over the combined arm:
  - R_m = min(mean `pL`, mean `pF`) / mean `pLF` (ratio of means);
  - R_g = min(gm `pL`, gm `pF`) / gm `pLF` (ratio of geometric means);
  - online time over all 576 points, bootstrap over points, 10,000
    resamples. The better single arm is chosen again inside every resample.
- **Decision rule.**
  - **Improvement** iff both 95% lower bounds exceed 1. The combination
    then becomes the new n = 83 one-target baseline.
  - **Regression** iff both upper bounds are below 1.
  - Otherwise **not_separated**.
  - The verdict is **invalid** if any of these fails: an exactness gate, the
    A/A (`pLF`/`pLFaa` inside [0.97, 1.03]), the planted control (`pX`/`pLF`
    lower bound above 1), or the completeness of all 576 points.
- **Also reported.** Combined vs each single arm and vs B, probe ratios, the
  new `S_rho` and its delta, the tuned-rho gap on the same points, a
  slice-level bootstrap (sensitivity to process-level effects), and the old
  panels as secondaries.
- **Exactness gates.** On every primary point:
  - `pL` reproduces `pB`'s probes and relation;
  - `pF`, `pLF`, `pLFaa` and `pX` have identical probes and relation;
  - one scalar across all six IC arms and the tuned rho, replayed as
    [d]G = Q in the pinned oracle.

  On the old panels every arm must reproduce the probes and relation
  archived for its order (`inputs/archived_identities.json`), and Q0 must
  equal the validation sidecar.
- **Power, checked before freezing** (`power_check.py`,
  `analysis/power.json`).
  - The simulation resamples the old held-out panel's measured
    left-major and Feistel times, and the 16 measured full / lift_scan
    ratios.
  - R_m has power near 1 at every size tried. R_g is the binding
    statistic, with an expected 1.27 against 1.45 for R_m.
  - 576 points give 0.87 power for the conjunction. That is the smallest
    size tried whose power stays at least 0.80 after subtracting two Monte
    Carlo standard errors.
  - If the order effect were only 1.30 on means (the stress scenario), the
    power would be 0.39. That scenario is reported, not sized for.
- **Runtime estimate.** About 2.2 to 3.2 h, including the build. There is a
  325 min time guard.

## Local validation (cloud-agent VM; no timing claims)

The VM is a shared 4-vCPU guest, so its clocks are not evidence. See
[`smoke/`](smoke/README.md) for the correctness-only receipt. In summary:

- Both crates build. The producer, rho and `lift2` tests pass, and B's
  factor-log table re-verifies.
- On primary points p000-p002, all six arms and the tuned rho are exact:
  - lift_scan matches the full scan's probes and relation;
  - the four Feistel arms are identical;
  - one scalar per point.
- On Q0 and the 16 fresh points, all four configurations reproduce the
  archived probes and relations of their order, and the archived scalars.

## Files

| File | Role |
| --- | --- |
| `protocol.json`, `make_protocol.py`, `schedule.json`, `make_schedule.py` | frozen protocol, its builder, frozen run order |
| `make_online_source.py`, `online/`, `lift2/` | combined producer (both parents' counted replacements), tuned rho, the two-limb canonicalizer crate |
| `restore.py`, `check_log_table.py` | restore and digest-check crypto 770f6a69 and every local source; re-verify B's factor-log table |
| `make_targets.py`, `inputs/primary_targets.json`, `inputs/old_heldout_targets.json` | the new primary panel; the old held-out panel, regenerated and compared |
| `inputs/archived_identities.json` | archived probes, relations and scalars per old point and order (exactness gates) |
| `power_check.py`, `inputs/power_prior.json`, `analysis/power.json` | power simulation and its prior |
| `arm.py`, `panels.py`, `run_schedule.py` | one arm per pinned process; panels; the schedule runner |
| `verify_receipt.py` | gates, statistics, decision rule; `result.json`, `result_table.md` |

## Limits

- Tier 1, instance-scoped: one runner, one pinned CPU, not host-isolated.
- Each IC process serves a 64-point slice warm, with one online interval
  per target and no shared target-dependent work. Process-level speed
  shifts are shared within a slice, which is why the slice bootstrap is
  reported.
- The tuned-rho gap is distance remaining. It is not a claim to beat rho.
