# The Constant in Front of √n

`ecdlp.tex` is a paper-quality LaTeX account of the measurements in this
library and in the sibling study repository
[aburan28/crypto](https://github.com/aburan28/crypto).

**Status**: anonymized for double-blind review. Restore real authors via
`make deanonymize` after creating an `AUTHORS` file (see `AUTHORS.example`).

## Building

Requires a TeX distribution (TeX Live, MacTeX, MiKTeX) with `pdflatex`,
`bibtex`, and the packages `amsmath`, `amssymb`, `amsthm`, `mathtools`,
`hyperref`, `booktabs`, `graphicx`, `xcolor`, `microtype`, `enumitem`,
`caption`, `tikz`, `pgfplots`. On Debian/Ubuntu:

```
sudo apt-get install texlive-latex-extra texlive-science texlive-fonts-recommended \
                     texlive-bibtex-extra latexmk poppler-utils
```

```
make           # PDF (pdflatex + bibtex + two more passes)
make check     # unresolved refs, overfull boxes, page count
make arxiv     # arxiv-submission.tar.gz
make eprint    # eprint-submission.zip
make deanonymize
make clean
```

Output: `ecdlp.pdf`. A built copy is committed so a reader without TeX
can open the paper.

## Contents

- Abstract.
- §1 Introduction, including the two-repository split (§1.5).
- §2 Method: boundary, one unit, one table, four classes.
- §3 Pollard rho: Teske walk, negation map, measured S, GPU emulator, fleet.
- §4 ECC2K-130: ONB arithmetic, CPU/GPU/FPGA, campaign, structural negatives.
- §5 Index calculus over prime fields, E(F_p)/E(F_{p^3}), genus 3/4 control.
- §6 Related work.
- §7 Conclusion.
- Appendix A: reproduction commands.

Every number is footnoted to a repository artefact. Companion CUDA rho
(256-bit), the ECC2K-95 kernel, and kangaroo code that have run only
through CPU emulation are kept out of headline claims.

## Companion artefacts

- This library: `docs/ALGORITHMS.md`, `docs/BENCHMARKS.md`, `docs/GPU.md`,
  `ecc2k130/`, `fpga/`, `src/rho.c`, `src/indexcalc.c`.
- Sibling: `docs/index-calculus-scoreboard.html`,
  `research/notes/index-calculus/`, `ecc2k130/`, `hdl/ecc2k130/`, `gpu/ecc/`,
  `gpu/ecc2k/`.
