# N83 one-target IC against strong rho: Tier 1 result

Protocol: [README.md](README.md) and `tier1_protocol.json`; receipt `tier1_github_38523707244/`.


Run `38523707244` (commit `5a1bb18d`, crypto `770f6a69`, `ubuntu-24.04` image
`ubuntu24` 20261004.327.1, AMD EPYC 9V74, 4 exposed CPUs, one pinned) ended with
conclusion success. The artifact is archived in
[`tier1_github_38523707244/`](tier1_github_38523707244/), and
`verify_tier1_receipt.py` re-run on the archived receipt (with the pinned crypto
source restored) reproduced `tier1_result.json`, `tier1_table.md` and the
workflow's verdict byte for byte. The rank stage passed (full rank, table
verified independently, Q0 verified, base hash matched); all 32 pairs are valid
and every claim check passed.

| Panel | Pairs | IC online median (ms) | rho online median (ms) | rho / IC primary [95%] | Frozen reading | Cold IC/rho | IC online / BL model |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| A: Q0, strong rho | 8 | 5,068 | 9,026 | 1.779 [1.775, 1.783] | `ic_online_faster` | 95.4 | 74.8 |
| B: 16 public points, strong rho | 16 | 645 | 6,200 | 2.769 [1.521, 8.990] | `ic_online_faster` | 134 | 33.5 |
| C: Q0, legacy packed rho | 8 | 5,110 | 38,500 | 7.536 [7.476, 7.600] | `ic_online_faster` (not a reference) | 23.1 | 1.10 |

**Verdict by the frozen rule.** Panel A reads `ic_online_faster` (lower bound
above 1), and it is the Tier 1 instance-scoped online result for Q0. It is quoted
with Panel B's section 23 figure (2.77, 12 of 16 rows IC faster), the cold ratio
and the BL column, and never as a speed of the method: the cold ratio is 95.4
(A) and 134 (B), and the break-even is 223 and 218 targets, so rho is ahead once
the 882 s setup (835.6 s rank stage plus per-process 46.5 s) is charged. Against
the BL model given that setup, IC online is 74.8x (A) and 33.5x (B) slower.
Panel C only tests the historical 8.2x: its median 7.54 [7.48, 7.60] excludes
8.2, so that figure did not survive isolation unchanged, and the packed rho is
not an accepted reference.

Limits and caveats:

* Panel A's interval covers eight repeats of one deterministic target, so it
  measures timing noise, not target variation. Rho took 1.42 times the floor
  steps on Q0 (mean over rows), against 0.995 over Panel B's 16 points, so Q0 is
  a long rho walk. Panel B has the target variation, and its wide interval
  is the honest width.
* One instance, one run, one CPU pinned on a shared cloud VM (Tier 1): not
  host-isolated, and exclusivity is not certified. `isolated_bench` marks Panel
  B `speedup_claim_eligible: false` by construction (it needs eight
  repetitions per case); the protocol's section 23 rule is used for B, as frozen.
* The precompute and the log-table load are instance observations, not
  noise-gated.
* It disagrees in direction with the 2026-10-12 crypto diagnostic (IC over
  strong rho 1.38 [1.04, 1.88], rho faster). The two differ in host, rho seed
  and index cache, and no reconciliation is claimed. No K or seed was
  re-chosen after seeing either result.
* The factor-log table (`precompute/factor_logs_n83_K600.json`, sha256
  `a771716f...d9f17e` with matching recomputation) is now archived; binding it
  in `tier1_protocol.json` is a separate, unmade change.

![rho/IC online ratio by panel with 95% intervals, and the earlier unisolated figures for scale.](figures/tier1_result.png)

## Replicate

Run `38532240007` was started unintentionally by a later commit that touched
this directory (the push filter did not yet exclude the result report). It ran
the same frozen protocol at commit `8dfd8606` on a different runner
(`GitHub Actions 1000295244`) and is archived as a **replicate** in
[`tier1_github_38532240007/`](tier1_github_38532240007/). It is reported beside
the first run and not pooled with it. The verifier reproduced its
`tier1_result.json`, `tier1_table.md` and verdict byte for byte; status
`COMPLETE`, all panels eligible, every claim check passed.

| Panel | Run 38523707244: rho / IC [95%] | Replicate 38532240007: rho / IC [95%] | Reading (both) |
| --- | --- | --- | --- |
| A: Q0, strong rho | 1.779 [1.775, 1.783] | 1.782 [1.771, 1.788] | `ic_online_faster` |
| B: 16 points | 2.769 [1.521, 8.990] | 2.771 [1.522, 8.993] | `ic_online_faster` |
| C: Q0, legacy packed rho | 7.536 [7.476, 7.600] | 7.763 [7.758, 7.827] | `ic_online_faster` (not a reference) |
| Cold ratio IC/rho (A / B) | 95.4 / 134 | 93.7 / 131 | |
| IC online / BL model (A / B) | 74.8 / 33.5 | 73.8 / 33.1 | |

Each run's reading stands on its own under the frozen rule. Panel B uses the
same 16 targets, and Panel A and C the same Q0 and rho seeds, in both runs, so
the replicate is not an independent sample of targets: it checks instance
(runner) and timing variation only. The caveats above, including the
unreconciled disagreement with the 2026-10-12 crypto diagnostic, apply to both.
The workflow's path filter now excludes receipts and report files, which stops
further retriggers and does not change the frozen protocol.

