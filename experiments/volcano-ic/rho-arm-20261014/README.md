# Matched rho arm for the n = 19 τ-invariant factor base (2026-10-14)

This experiment reruns the baseline subspace IC arm and the τ-orbit dim-6 IC
arm on E0/F_2^19 (`EC1N19Ckb1h01617b86df6c`, r = 130873). A matched
signed-Frobenius Pollard rho arm runs with them, on the same ten planted
scalars, interleaved, in one process on one host. The frozen design is in
`protocol.json`. The preregistration report, with its diagram and validation
graph, is `preregistration-20261014.md` (PDF beside it).

**Status: measured (GitHub run `38520305068`, exploratory tier).** The run
completed with conclusion success: 10 of 10 scalars with all three arms
verified, 640/640 rho logs verified, S_steps 0.2028 (0.997x the floor), validity
gate passed. `results/`, `report/` (report.md, report.pdf) and `figures/arms.*`
are the workflow artifact; re-running
`python3 analyze.py results` (plain Python) on a copy reproduced `summary.json` and `report.md`
byte for byte.

Frozen decisions (`protocol.json`), CPU per complete ECDLP, geometric mean with
95% bootstrap interval:

| comparison | ratio | rule outcome |
| --- | --- | --- |
| baseline base / rho | 1.77e5 (1.66e5-1.89e5) | costs more than matched rho: not an advance against rho on E0/F_2^19 |
| tau-orbit base (dim 6) / rho | 1.94e4 (1.69e4-2.23e4) | costs more than matched rho: not an advance against rho |
| baseline / tau-orbit base | 9.124 (8.122-10.270) | the orbit-base speedup replicates within this run |

The 2026-09 numbers in `../README.md` (444 s, 70 s, 6.85x) were not used in these
statistics. The tier is exploratory: a GitHub-hosted VM (AMD EPYC 9V45, 4
logical CPUs, no allocation receipt or pinned CPU), so there is no Tier 1 claim.
The 9.12x is this run's replication value and does not replace 6.85x. Graph:
`figures/arms.png`; report PDF: `report/report.pdf`.

```sh
python3 validate_rho.py                    # pure Python: correctness + step counts (no Sage needed)
sage arms.sage selftest                    # Sage backend == Python backend, 8 identical walks
sage arms.sage run --out results           # the frozen protocol (hours)
sage -python analyze.py results            # summary.json, report/report.{md,pdf}, figures/arms.{svg,png}
python3 prereg_figures.py                  # figures/protocol.*, figures/validation-steps.*
pandoc preregistration-20261014.md -o preregistration-20261014.pdf --pdf-engine=pdflatex -H pdf-header.tex
```

The measurement runs in GitHub Actions
(`.github/workflows/volcano-ic-n19-rho-arm.yml`):

- It runs on `ubuntu-24.04`, inside `sagemath/sagemath:10.10` pinned by digest.
- It starts on a push to `claude/frobenius-orbit-canonicalization-gwmz8z` that
  touches this directory or the workflow, or on `workflow_dispatch`.
- It uploads `results/`, `report/` and `figures/arms.*` as an artifact.

Pure-Python validation (`validation/local-validation.json`): 640/640 rho logs
are verified. The mean is 73.4 steps, S_steps = 0.2028 (95% CI 0.1943–0.2112),
which is 0.997× the floor √(π/(4·19)) = 0.2033. A stress run with R = 2 and no
look-ahead had 206 fruitless cycles in 200 solves; all were escaped and
200/200 logs were verified.
