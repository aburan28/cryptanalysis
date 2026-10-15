---
title: "lift_scan x Feistel order: the combined n = 83 K600 one-target index calculus"
date: 2026-10-15
---

# lift_scan x Feistel order: the combined n = 83 K600 one-target index calculus

**Status (2026-10-15): measured; frozen primary rule applied; verdict
`not_separated`. No new baseline.** GitHub Actions run
[38803625711](https://github.com/aburan28/cryptanalysis/actions/runs/38803625711)
(attempt 1, one `ubuntu-24.04` runner, AMD EPYC 7763, Tier 1 instance scope)
ran the frozen [protocol](protocol.json) and [schedule](schedule.json). Its
artifact `n83-combined-38803625711-1` is archived in
[`run_github_38803625711/`](run_github_38803625711/). Against the better
single arm (lift_scan only), the combination is **1.236 [1.067, 1.428]** on
means (R_m) and **1.061 [0.908, 1.243]** on geometric means (R_g). R_m clears
1; R_g does not, so the rule says `not_separated`. See [Result](#result).

## Question

Two measured, promoted n = 83 a = 1 K600 one-target IC improvements change
different factors of the online cost:

- **lift_scan** (PR #926, `claude/n83-liftscan` @ 8f6b4057e,
  run 38776966036) replaces the 83-rotation partner-root canonicalizer with the
  exact two-limb `lift_scan`. It cuts ns/probe by 1.515 [1.506, 1.525] and
  leaves the probes unchanged.
- **Feistel scan order** (PR #927, `claude/n83-scan-order` @ af41562e7,
  run 38786433493) visits the same index states in a keyed pseudo-random order
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
| `run_github_38803625711/` | the archived artifact: allocation, builds, raw runs, `panel/result.json` |
| `make_figures.py`, `figures/` | result figure (TikZ source, PDF, PNG) |
| `README.pdf` | this report: `pandoc README.md -o README.pdf --pdf-engine=pdflatex -H report_header.tex --lua-filter report_filter.lua -V geometry:margin=2cm -V fontsize=10pt -V colorlinks=true` |

## Result

All 662 scheduled rows are valid (576 primary points, 384 old held-out, 17
Q0 + fresh; no time-guard trip). Every exactness gate passes, the A/A and the
planted control pass, and the primary panel is complete.
`verify_receipt.py` re-run on the archive reproduces `result.json` byte for
byte. One tuned-rho row (serial 5) carries a major-page-fault flag; it is a
rho row, not an IC arm, and the verifier keeps it in the receipt.

![Frozen ratios with 95% bootstrap intervals, all from `result.json`
([source](figures/result.tex), [vector](figures/result.pdf), rendered by
[`make_figures.py`](make_figures.py)).](figures/result.png)

### Primary (frozen rule, applied literally)

The combination is an improvement only if both 95% lower bounds exceed 1.

| Statistic (n = 576 new points) | Estimate [95%] | Reading |
| --- | --- | --- |
| R_m = min(mean pL, mean pF) / mean pLF | 1.2363 [1.0671, 1.4276] | lower bound above 1 |
| R_g = min(gm pL, gm pF) / gm pLF | 1.0611 [0.9083, 1.2430] | lower bound below 1 |

**Verdict: `not_separated`.** The R_g interval includes 1, so the frozen rule
does not promote the combination. The better single arm is pL (lift_scan
only) in both statistics' point estimates.

### Secondaries (none changes the verdict)

- **Means-only reading.** R_m alone would read `improvement`. The protocol
  made the conjunction the rule, and R_g is the statistic the power check
  named as binding (expected 1.27; observed 1.06). The slice-level bootstrap
  of R_m (9 slices) gives 1.2363 [1.1005, 1.3957].
- **Combined against each single arm and against B** (ratio of means, then
  geometric means):

| Contrast | Means [95%] | Geomeans [95%] |
| --- | --- | --- |
| combined vs lift_scan only | 1.2363 [1.0733, 1.4307] | 1.0611 [0.9055, 1.2435] |
| combined vs Feistel only | 1.5994 [1.5965, 1.6023] | 1.5985 [1.5962, 1.6009] |
| combined vs B | 1.9992 [1.7285, 2.3090] | 1.7143 [1.4646, 2.0080] |

lift_scan only vs B is 1.6171 [1.6156, 1.6186] on means; Feistel only vs B
is 1.2500 [1.0825, 1.4408]. The probe ratio B / Feistel is 1.2523
[1.0877, 1.4430]. The two single effects multiply on means (1.25 × 1.62 =
2.02, against 2.00 observed for the combination). On geometric means the
order effect is small (Feistel vs B 1.0724 [0.9129, 1.2546]), which is why
R_g is the binding statistic. We have not tested why; that is a reading, not
a result.

- **Online means (ms).** pB 1072.8, pL 663.4, pF 858.3, pLF 536.6, pLFaa
  532.3, pX 927.8. Probes per law: B and lift_scan 1.256, Feistel arms 1.003.
- **S_rho** (online cost over √r in tuned-rho steps; the unit is this run's
  measured rT770 step): pB 0.04137, pL 0.02558, pF 0.03310, pLF 0.02069.
  Delta S_rho: combined minus better single (pL) = −0.00489; combined minus
  B = −0.02068. These are online S only; no cold S was measured.
- **Gap to tuned rho** (rT770 on the same 576 points). Tuned rho / combined
  is 4.6628 [4.2501, 5.1308] on means and 7.2786 [6.5115, 8.1684] on
  geometric means; the same figure for B is 2.3323 [2.0713, 2.6339]. So the
  online interval of the combination is about 0.214 of tuned rho's on means
  (inverse of 4.66). This is distance and not a gate; it is online only, and
  the precomputation is not in it.
- **Controls.** A/A pLF / pLFaa = 1.0081 [1.0058, 1.0104], inside the frozen
  [0.97, 1.03]. Planted pX / pLF = 1.7290 [1.7256, 1.7321], lower bound above
  1.
- **Old panels (secondary).** Held-out 384: R_m 1.4710 [1.2283, 1.6213]
  (`improvement`), R_g 1.2942 [1.0757, 1.5564], combined vs B 2.3876
  [1.9776, 2.8539]. Q0 + 16 fresh (one block of 16): R_m 1.6237
  [0.9876, 1.6270], combined vs B 5.5007 [1.6284, 11.9937]; n = 16 is too
  small to read.

### Reading

- The primary rule is not met. The combination is clearly faster than B
  (about 2.0× on means, 1.7× on geometric means), and it beats Feistel alone
  by 1.60× on both. Against lift_scan alone it separates on means but not on
  geometric means.
- The held-out panel, a separate and larger-effect sample, does separate on
  both statistics, so the not-separated verdict is about this panel's R_g,
  not evidence of no effect. It is a secondary and does not change the rule.
- Ratchet: no new baseline from this experiment. See
  [`docs/ic/BASELINES.md`](../../docs/ic/BASELINES.md).

### Process note

A collector stopped by a container restart was replaced; nothing was
archived before this result, and no run was repeated.

## Limits

- Tier 1, instance-scoped: one runner, one pinned CPU, not host-isolated.
- Each IC process serves a 64-point slice warm, with one online interval
  per target and no shared target-dependent work. Process-level speed
  shifts are shared within a slice, which is why the slice bootstrap is
  reported.
- The tuned-rho gap is distance remaining. It is not a claim to beat rho.
