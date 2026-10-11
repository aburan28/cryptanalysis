# Papers

Every manuscript generated from this library's measurements lives here, one
directory per paper, each with its own `Makefile`, `README.md`, `abstract.txt`
and a committed built PDF so a reader without TeX can open it. Shared LaTeX
build artefacts are ignored by `papers/.gitignore`.

| directory | title | status |
|---|---|---|
| [`ecdlp-constant/`](ecdlp-constant/) | The Constant in Front of √n: Measured Pollard Rho, ECC2K-130 Arithmetic, and Index Calculus over Prime Fields | research draft, anonymized |
| [`frobenius-orbits/`](frobenius-orbits/) | Efficient Signed-Frobenius Orbit Canonicalization and Phase-Aware Representations for Elliptic-Curve Index Calculus | research draft, anonymized |

Conventions shared by every paper here:

- every number is footnoted (the `\art{}` macro) to a committed artefact in
  this library, the sibling `crypto` repository (`crypto:` prefix) or the
  research ledger (`crypto-autoresearcher:` prefix);
- stage diagnostics are never reported as speedups, every end-to-end row has
  verified answers, and every change is classed as advance, engineering,
  relabelling or accounting;
- `make check` must pass (all references resolved, no overfull boxes) before
  the PDF is recommitted, and the PDF is refreshed whenever a cited conclusion
  or figure changes;
- authors are anonymized in the sources; `make deanonymize` restores them from
  an `AUTHORS` file (see `ecdlp-constant/AUTHORS.example`).

Add a new paper as a new subdirectory and a row in the table above. The
sibling repositories keep their own: `crypto/paper/` and
`crypto-autoresearcher/papers/`.
