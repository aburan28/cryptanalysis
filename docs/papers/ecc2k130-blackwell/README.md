# ECC2K-130 on Blackwell: research manuscript

**Author:** Adam Buran  
**Intended destination:** IACR Cryptology ePrint Archive  
**Status:** Research preprint draft, September 21, 2026. Prepared locally; not submitted or published.

The manuscript reports the frozen `warps4_poly_compact640` acceptance result:

| Measure | Result |
| --- | ---: |
| Candidate median, five confirmation samples | 22.100934 billion scheduled scalar-slot updates/s |
| Same-session baseline median | 19.852741 billion updates/s |
| Ratio-of-medians improvement | 11.3243% |
| DP34 collection, one separate sample | 21.548499 billion updates/s |
| Collection records / drops | 12,387 / 0 |

The paper specifies the accounting and timer boundaries, explains why DP34 is a Hamming-weight threshold, and separates the table walk from the historical Frobenius iteration. It does not assert a completed challenge solution, a global fastest-solver record, or a measured fleet-wide speedup.

## Files

- `paper.tex`: complete manuscript, mathematical derivations, numbered algorithm, tables, and appendices.
- `references.bib`: ten references, including primary literature, NVIDIA documentation, and the local research artifact.
- `figures/confirmation-rates.pdf`: vector plot of every confirmation rate.
- `architecture.mmd`: editable Mermaid sequence diagram corresponding to the implementation.
- `evidence/measurement.json`: unmodified archived receipt, including raw benchmark and probe output.
- `evidence/acceptance.json`: unmodified acceptance record and known limitations.
- `evidence/source-manifest.json`: original 119-file source manifest, complete build command, and measured executable identity.
- `evidence/analysis.json`: locally recomputed statistics and arithmetic-verification results.
- `analyze_evidence.py`: local analysis and figure generator; no GPU or cloud launch.
- `claims-map.md`: claim-to-evidence map for editorial review.

The final PDF is placed at the repository root under `output/pdf/ecc2k130-blackwell-buran.pdf`.

## Build the paper

From this directory, with Tectonic available:

```sh
tectonic paper.tex
```

Alternatively use an ordinary LaTeX distribution:

```sh
pdflatex paper.tex
bibtex paper
pdflatex paper.tex
pdflatex paper.tex
```

The included figure is sufficient for a standalone manuscript build. The source package does not require running a cryptographic workload.

To recheck the archived implementation and regenerate the figure in the original repository, use Python 3 with matplotlib:

```sh
python3 docs/papers/ecc2k130-blackwell/analyze_evidence.py
```

This analysis expects `ecc2k130/research/candidates/goal22/` in the same repository. It verifies every source hash, exact timing counts, medians, corpus identities, checkpoint results, the generated square header, general polynomial reduction, and the internal polynomial's irreducibility. GPU checks are read from the archived receipt, not rerun locally.

## Editorial boundary

The author and destination follow the requested attribution. No affiliation, email address, funding acknowledgment, submission identifier, or acceptance status has been invented. The manuscript uses an ordinary single-column academic preprint layout; it does not claim to be an official IACR proceedings template.

The main issues for author review are the rare exceptional affine inputs, the collision behavior of history-dependent cycle avoidance, one-device sampling, and the unavailable Compute Sanitizer / inherited `test-clmad` failures. These appear in the paper itself. The included local artifact reference should be replaced or supplemented by a stable public deposit before submission. The original binary report corpora and measured executable are identified by hash but are not bundled with the manuscript.
