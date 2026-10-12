# Papers

Every manuscript generated from this library's measurements lives here, one
directory per paper.

| directory | title | status |
|---|---|---|
| [`ecdlp-constant/`](ecdlp-constant/) | The Constant in Front of √n: Measured Pollard Rho, ECC2K-130 Arithmetic, and Index Calculus over Prime Fields | research draft, anonymized, not submitted |
| [`frobenius-orbits/`](frobenius-orbits/) | Efficient Signed-Frobenius Orbit Canonicalization and Phase-Aware Representations for Elliptic-Curve Index Calculus | research draft, anonymized, not submitted |

Conventions shared by every paper here and by the sibling repositories
(`aburan28/cryptanalysis`, `aburan28/crypto`, `aburan28/crypto-autoresearcher`,
`aburan28/ml-cryptanalysis`), as set out in the "Papers" section of `AGENTS.md`:

- one directory per paper, holding the root `.tex` (or the `.md` of a draft not
  yet typeset), its sections and bibliography, a `README.md` (status banner,
  what it says, what it does not say, how to build, reproduction pointers, the
  checklist owed before submission), an `abstract.txt` and the built PDF;
- the build is `paper.mk` in this directory: a paper's `Makefile` sets `TEX`,
  `SECTIONS` and `BIB` and includes it (`make`, `make check`, `make arxiv`,
  `make eprint`, `make deanonymize`, `make clean`);
- every number cites a committed artefact in this repository or a sibling
  (`crypto:`, `cryptanalysis:` or `crypto-autoresearcher:` prefix); a stage
  diagnostic is never reported as a speedup; every end-to-end row has verified
  answers; every change is classed as advance, engineering, relabelling or
  accounting;
- `make check` must pass (references and citations resolved, no LaTeX errors,
  no overfull boxes) before a PDF is recommitted, and the PDF is rebuilt
  whenever a cited number, conclusion or figure changes;
- sources are anonymized (`\author{Anonymous}`); `make deanonymize` restores
  the authors from an untracked `AUTHORS` file copied from `AUTHORS.example`.

Add a new paper as a new subdirectory and a row in the table above.
