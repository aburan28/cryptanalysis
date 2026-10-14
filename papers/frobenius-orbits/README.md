# Efficient Signed-Frobenius Orbit Canonicalization and Phase-Aware Representations for Elliptic-Curve Index Calculus

`main.tex` is a paper-quality LaTeX draft about the *representation* under
Koblitz-curve index calculus with a Frobenius-invariant factor base: the
signed-Frobenius form `P = ε·τ^{-k}(P̂)`, an exact shortcut for the
normal-basis least-rotation canonical form, the memory layouts that carry the
phase `k` from the decomposition stage to the relation matrix, and benchmarks
of what survives complete relation collection. It is framed as an
algorithmic/engineering paper with proofs and reproducible measurements. It
claims no ECDLP attack, no asymptotic statement, and no end-to-end advance over
Pollard rho. Every row that charges the index calculus's setup is slower than
the matched signed-Frobenius rho. The isolated single-target rows where it is
faster *online* (8.8–17.5× at r ≤ 2^47, 12.9–13.9× at n = 61) exclude that
setup, and a Bernstein–Lange walk given the same precomputation is modelled to
be 2–8× faster still (§7).

**Status**: research draft, not peer-reviewed, not submitted, not posted.
Anonymized for double-blind review; restore authors with `make deanonymize`
after creating an `AUTHORS` file (see `../AUTHORS.example`).

Every number is footnoted to a committed artefact in this library (paths
without a prefix), the sibling [aburan28/crypto](https://github.com/aburan28/crypto)
(`crypto:` prefix) or the research ledger
[aburan28/crypto-autoresearcher](https://github.com/aburan28/crypto-autoresearcher)
(`crypto-autoresearcher:` prefix). Appendix A lists them by section.

## Building

Same toolchain as the companion paper in `../ecdlp-constant/`; the build rules are the shared `../paper.mk`: `pdflatex`, `bibtex`, and the
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

1. ~~**Novelty audit**~~ — done 2026-10-14.
   - GGMP (SAC 2020) was read in full in both the preproceedings and the
     peer-reviewed (Birmingham repository) versions; their texts agree on every
     statement cited, and the orbit representative is chosen "in an ad-hoc
     manner" and never priced in either.
   - Bailey et al. 2009 §3 normalizes distinguished points to the
     lexicographically smallest normal-basis conjugate and avoids per-step
     canonicalization by using a Hamming-weight Frobenius walk. It is credited
     as the canonical form.
   - The zero-gap lemma is **not new as combinatorics**. That a necklace begins
     with a longest run of its least letter is standard: Ruskey–Sawada 1999
     §3.2 use its density consequence, and Gabrić–Sawada 2026 Definition 3
     makes it the first clause of a quasinecklace.
   - The paper now states the lemma as a standard fact. Its claim is narrowed
     to using that fact as an exact word-level filter, plus the two
     implementations, their exactness proofs and the measurements (§1, §4,
     §8, §9, abstract).
2. ~~**Isolated replay** of the `n = 83` zero-gap stage~~ — measured, Tier 1
   (GitHub run `38502816475`, one `ubuntu-24.04` instance, 16 pairs, all gates
   passed), in
   `experiments/koblitz-n83-index-design-20260929/packed_index_e1_canonical_tier1_20261014/`.
   - Frozen rule: `promoted`. Canonicalization-phase ratio 1.086
     [1.076, 1.094]; target stage 1.023 [1.017, 1.033]; negative control 1.007
     [0.997, 1.017].
   - The exploratory 1.42× is `refuted_overstated`; the paper now reports the
     Tier 1 figure (stage diagnostic, one target, one instance; not a complete
     speedup). Still open: Tier 0 host isolation, if a speedup claim beyond the
     instance is wanted.
3. **Isolated one-target comparison at `n = 83`.**
   - The historical 8.2× used a packed rho that crypto no longer accepts.
     Against the current strong rho on the same point, IC is 1.38× *slower*
     online (diagnostic; `crypto:research/n83_evaluation_20261012/`).
   - A Tier 1 GitHub-runner protocol extends the n = 61 isolated `vs_rho`
     protocol to n = 83, in
     `experiments/koblitz-single-target-n83-tier1-20261014/`:
     - Panel A: strong rho on Q0, 8 pairs.
     - Panel B: 16 fresh public points.
     - Panel C: the legacy packed rho.
     - Each panel reports the cold ratio and the Bernstein–Lange column.
   - The protocol has been pushed but not read back.
4. A **rho arm at `n = 19`** is preregistered in
   `experiments/volcano-ic/rho-arm-20261014/`. It is a matched signed-Frobenius
   rho run in the same job as fresh baseline and Γ-orbit arms, in a pinned Sage
   container on a GitHub runner, so the result will be exploratory tier. The
   workflow has been pushed but not read back. Until then, `6.85×` stays a
   ratio between two bases, not a ratio to rho.
4a. ~~**n = 131 canonicalization**~~ — measured in
   `experiments/canon-n131-20261014/` (three limbs, exact; instruction counts
   only). The branch-free arm is 2.4× the exhaustive scan; the binary-lifting
   variant A form is cheapest. Proposition `prop:cost` was corrected: variant
   B's ctz scan is Θ(n) steps.
5. ~~Independent re-derivation~~ — done 2026-10-14, with limited
   independence (a separate AI agent session that did not write the draft,
   not a human). See `review/rederivation-20261014.md`.
   - Result: 56 MATCH, 13 MISMATCH, 3 DERIVED-ONLY, 0 UNSOURCED, in 72 rows.
   - All 13 mismatches are corrected in this draft. Among them: the 18-byte
     record table (2.27×, not 2.50×); the tier range (12.1–15.4× rho); the
     n = 61 pipeline (330.7× rho, not 12–13×); and cross-experiment sentences
     now name their experiments.
   - The most important correction is to the claim that nothing beats rho
     online. Isolated single-target rows at n = 41–61 show the index calculus
     faster online with its setup excluded. §7, the abstract and §9 now give
     both the online and the cold readings, plus the Bernstein–Lange model.
   - Still weakly sourced: the variant C ns figures (a doc comment only) and
     `tab:canon-cost` (a research-note table, no raw run record).
6. Replace the `ecdlpconstant` companion citation with its ePrint number once
   it has one.
