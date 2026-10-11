# Efficient Signed-Frobenius Orbit Canonicalization and Phase-Aware Representations for Elliptic-Curve Index Calculus

`main.tex` is a paper-quality LaTeX draft about the *representation* under
Koblitz-curve index calculus with a Frobenius-invariant factor base: the
signed-Frobenius form `P = ε·τ^{-k}(P̂)`, an exact shortcut for the
normal-basis least-rotation canonical form, the memory layouts that carry the
phase `k` from the decomposition stage to the relation matrix, and benchmarks
of what survives complete relation collection. It is framed as an
algorithmic/engineering paper with proofs and reproducible measurements. It
claims no ECDLP attack, no asymptotic statement, and no end-to-end advance over
Pollard rho; every end-to-end row is slower than the matched signed-Frobenius
rho and says so.

**Status**: research draft, not peer-reviewed, not submitted, not posted.
Anonymized for double-blind review; restore authors with `make deanonymize`
after creating an `AUTHORS` file (see `../AUTHORS.example`).

Every number is footnoted to a committed artefact in this library (paths
without a prefix), the sibling [aburan28/crypto](https://github.com/aburan28/crypto)
(`crypto:` prefix) or the research ledger
[aburan28/crypto-autoresearcher](https://github.com/aburan28/crypto-autoresearcher)
(`crypto-autoresearcher:` prefix). Appendix A lists them by section.

## Building

Same toolchain as the companion paper in `../`: `pdflatex`, `bibtex`, and the
packages `amsmath`, `amssymb`, `amsthm`, `mathtools`, `hyperref`, `booktabs`,
`tabularx`, `graphicx`, `xcolor`, `microtype`, `enumitem`, `caption`,
`algorithm`, `algpseudocode`, `natbib`, `url`.

```
make           # PDF (pdflatex + bibtex + two more passes)
make check     # unresolved refs/citations, overfull boxes, page count
make arxiv     # arxiv-submission.tar.gz
make eprint    # eprint-submission.zip
make deanonymize
make clean
```

Output: `main.pdf` (about 25 pages). A built copy is committed so a reader
without TeX can open the paper.

## Contents

- Abstract (`sec-abstract.tex`).
- §1 Introduction and contributions.
- §2 Preliminaries: Koblitz curves, the signed-Frobenius group, the
  free-action lemma (orbits are full for prime `n`; the exceptional words are
  exactly `x ∈ F_2`), normal bases, the GGMP factor-base reduction recalled.
- §3 The signed-Frobenius representation: definition, logarithm transport, the
  Frobenius-invariant sign chooser `Tr(y/x)`, phase-aware relations and the
  reconstruction theorem.
- §4 Canonicalization by cyclic zero gaps: the lemma, uniqueness for prime `n`,
  the two implemented variants (bit-parallel run growth for one-word fields;
  set-bit scan for two-limb fields) and the vectorized exhaustive scan,
  correctness including the exceptional words, cost.
- §5 Phase-aware memory layouts: representatives on disk, the 18-byte packed
  root record with a 7-bit phase, the skew of canonical keys (never index by
  leading bits), the folded pair table, the row filter and the orbit tag.
- §6 Carrying the phase through a pipeline: the four representative
  conventions in the code, the Rust index-calculus data flow, the matched
  signed-Frobenius rho reference, the `n = 83` root index, the `n = 19` Sage
  pipeline.
- §7 Benchmarks: measurement contract (unit `S`, classes, isolation,
  correctness); canonicalization cost; the canonicalization inside the rho
  reference (instruction-counted ladder); orbit compression of tables (fold at
  equal memory, probe shapes, tier crossover in operations, packed index, cold
  jobs, SAT encodings); end to end with verified logarithms (`n = 19` Gröbner,
  `n = 61` pipeline, isolated cold panel at `n = 37–53`, the `n = 83`
  observation); what survives.
- §8 Related work and what is not new (Bailey et al.'s normalization is the
  canonical form; GGMP is the factor-base reduction).
- §9 Limitations and claims not made, including why the internally circulated
  "131×" and "18.9×" figures are cost ratios, not speedups.
- §10 Conclusion. Appendix A: reproduction.

## Before submission

1. **Novelty audit** against Galbraith–Granger–Merz–Petit (SAC 2020) in full
   text (the ledger's note is abstract-only) and against Bailey et al. 2009 for
   the canonical form; confirm no prior statement of the zero-gap lemma.
2. **Isolated replay** of the `n = 83` zero-gap stage through
   `experiments/koblitz-n83-index-design-20260929/packed_index_e1_isolated_replay_20261010/`
   so the canonicalization timing ratio can be promoted from exploratory.
3. **Isolated one-target comparison at `n = 83`** (the only observation where
   a phase-aware index calculus is ahead of rho; currently unisolated).
4. Decide whether to keep the `n = 19` Gröbner comparison as the only
   end-to-end positive row or to add a rho arm at `n = 19` so its `6.85×` is
   read against the right reference.
5. Independent re-derivation of the numbers in Tables 1–8 from the cited
   artefacts by someone who did not write the draft.
6. Replace the `ecdlpconstant` companion citation with its ePrint number once
   it has one.
