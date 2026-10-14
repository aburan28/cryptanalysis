# Matched rho arm for the n = 19 τ-invariant factor base (2026-10-14)

This experiment reruns the baseline subspace IC arm and the τ-orbit dim-6 IC
arm on E0/F_2^19 (`EC1N19Ckb1h01617b86df6c`, r = 130873). A matched
signed-Frobenius Pollard rho arm runs with them, on the same ten planted
scalars, interleaved, in one process on one host. The frozen design is in
`protocol.json`. The preregistration report, with its diagram and validation
graph, is `preregistration-20261014.md` (PDF beside it).

**Status: proposed, not yet measured.** No CPU number here is a result. The
2026-09 numbers in `../README.md` (444 s, 70 s, 6.85×) are not compared with
anything this run produces.

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
