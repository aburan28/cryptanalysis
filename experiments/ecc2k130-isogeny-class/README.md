# ECDLP hardness across the ECC2K-130 isogeny class

How hard is the discrete logarithm on each curve that is F_q-isogenous to ECC2K-130
(`E0: y^2 + xy = x^3 + 1` over `F_{2^131}`)? The class splits into four endomorphism
levels (conductors 1, 263, p, 263p with p = 146505763881528721). This directory holds the
per-curve validation of E0 and all 262 conductor-263 floor curves, the analysis of the two
unenumerated levels, and a review of the earlier Codex "volcano descendant" investigation.

Read [`REPORT.md`](REPORT.md) or the typeset
[`ecc2k130_isogeny_class_hardness.pdf`](ecc2k130_isogeny_class_hardness.pdf) first.

## Result

| Level (conductor) | Curves | Native rho (log2) | Effective (log2) |
|---|--:|--:|--:|
| 1 (E0) | 1 | 60.81 | 60.81 |
| 263 (floor) | 262 | 64.33 | 60.81 (verified 263-isogeny to E0, <= 2^15.6 F_q-mults) |
| p | p + 1 ~ 2^57.0 | 64.33 | in [60.81, 64.33] |
| 263p | 262(p + 1) ~ 2^65.1 | 64.33 | in [60.81, 64.33] |

No curve in the class is easier than E0. The p-level interval closes only if someone builds
a characteristic-2 higher-dimensional (Kani) isogeny pipeline; constructing any such curve
costs about 2^70 F_q-multiplications, more than solving natively on it.

## Layout

| Path | Contents |
|---|---|
| `REPORT.md`, `ecc2k130_isogeny_class_hardness.pdf` | the report (11 pages, per-curve appendix) |
| `data/per_curve_hardness.csv` | 263 rows x 19 columns: level, j, b, order, End certificate, embedding degree, GHS magic number, rho class size, native/effective rho, transport cost, IC density z-score |
| `data/hardness_by_level.csv` | one row per level |
| `data/claims_ledger.json`, `data/verify2_results.json` | every sweep claim with its recompute/audit verdicts and corrections |
| `ground_truth/` | builds the 263 curves from `H_{-7*263^2}` mod 2, point-counts both twists, reproduces the Codex labels; `ecc2k.py` is the loader |
| `ground_truth_check/` | independent derivation of the 262 floor j-invariants by Velu from `E0[263]` (262/262 match) |
| `sweeps/<vector>/` | one directory per attack vector (group order, endomorphism ring, pairings, GHS, rho endomorphisms, 263-transport, p-levels, index calculus, two toy analogues, Codex cross-check, literature): scripts, `report.md`, `per_curve.json` |
| `gaps/G1..G6/` | completeness-critic gap fills (independent re-verification of rho endomorphisms and GHS, index-calculus cost model, p-level/literature reconciliation, n = 131 per-curve Semaev runs, 48,220-comparison cross-check) |
| `redteam/` | 44 attack ideas with the computations behind each self-assessment |
| `codex-review/REVIEW.md` | run-by-run review of the Codex Runs 01-13 |
| `report/` | scripts that merge the per-curve table, build the claims ledger, and render the figures and PDF |
| `verification-workspace.tar.xz` | the adversarial verifiers' working directories (scripts, notes, outputs <= 64 KB), 1,751 files; verdicts are summarised in `data/` |

## Reproducing

Scripts were written against a scratch root `/Volumes/SSD990/ecdlp-hardness-work`; that path is
hardcoded in many of them. To rerun, either recreate that layout (copy this directory there,
with `sweeps/*` and `gaps/`, `redteam/` moved to the top level) or edit the constant at the top
of the script. Requirements: SageMath 10.x (PARI inside), Python 3, a C compiler; msolve for the
Semaev runs.

```sh
cd ground_truth && TMPDIR=$PWD/../tmp sage -python build_ground_truth.py   # ~1 min, stops on the first failed check
cd ../ground_truth_check && sage -python derive_floor.py                    # Velu cross-check
```

The figure and PDF scripts in `report/pdf/` read the scratch layout (`toy-b/`, `index-calculus/`,
`report/per_curve_hardness.csv` under the scratch root), so run them from a recreated scratch root.

No attempt was made on the ECC2K-130 challenge DLP; every solved DLP is a toy instance with a
planted logarithm.
