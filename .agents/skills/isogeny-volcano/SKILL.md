---
name: isogeny-volcano
description: Walk the ℓ-isogeny volcano (ℓ = 2 or 3) of a prime-field curve with `ca volcano`, carry one ECDLP instance by verified Vélu isogenies to every stratum, measure Pollard rho (ca_rho_solve) on each curve — min / mean / max per curve and per level, with isomorphic controls — and land the standard volcano diagram and report. Use whenever someone asks to walk an isogeny graph or volcano, or compare ECDLP cost across isogenous curves or volcano levels.
---

# Isogeny volcano with `ca volcano`

The canonical workflow lives in aburan28/crypto at
`.agents/skills/isogeny-volcano/SKILL.md`: framing, curve choice, how to
read the results, the report, the PDF and the benchmark entry. Follow it.
Here the binary is `ca`, with the module in `ca_volcano.h` /
`src/volcano.c`:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target ca
./build/ca volcano --p P --a A --b B [--order N] [--ell 2|3] [--seed S] \
    [--trials 100] [--per-level 10] [--controls 3] [--threads T] [--no-negation] \
    --diagram run/volcano.diagram.json --trials-out run/trials.csv > run/results.json
```

- **What it does:** it counts points (or checks `--order`), draws `P` of
  prime order n and `Q = kP` from `--seed`, and walks the volcano. Every
  edge is checked: image on the codomain, a homomorphism, order kept. A
  walk where an edge skips a level is refused. It then runs rho on the
  root, up to `--per-level` curves per level and `--controls` isomorphic
  re-scalings.
- **Output:** JSON on stdout, a table on stderr. The exit status is 1 if
  any solve misses `k`.
- **Reference:** expect about `√(πn/4)` group operations with the
  negation map (the default) and `√(πn/2)` with `--no-negation`. Tiny
  groups show `ca`'s fixed setup cost.
- **Diagram:** render `--diagram` output with the standard renderer
  `tools/volcano-diagram/volcano_diagram.py` in aburan28/crypto
  (research-visuals, "Isogeny volcanoes: the standard diagram").
- **Cross-check:** `volcano-rho` in aburan28/crypto walks the same
  volcanoes with independent code. `tests/test_volcano.c` pins that both
  give curve A of its `research/isogeny-volcano-rho/` study as 80 curves,
  2 / 6 / 18 / 54.
- **Scope:** this measures rho against rho. It is not an index-calculus
  result, and a curve's level is not a speedup unless its mean beats the
  control's spread.
