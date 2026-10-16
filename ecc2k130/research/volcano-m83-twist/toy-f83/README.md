# F_83 toy: factor-base tournament over 7-isogenous, rescaled models (2026-10-16)

Independent reproduction of a screenshot from another session ("Measure Factor Base Yield"): instance
G = (26, 58), Q = (61, 82), Q = 17G, subgroup order 41, with a degree-7 isogeny to y² = x³ + x + 16.

- The instance is **not** short Weierstrass: the only y² = x³ + ax + b through G and Q is a = 6, b = 74
  (supersingular, 84 points, ord G = 42, Q = 19G). The general model y² = x³ + x² + 2x fits (82 points,
  ord G = 41, Q = 17G; short form A = 57, B = 24, j = 52).
- `iso7.py`: exact 7-isogenies from the 7-division polynomial and Vélu. The class with 82 points has
  j ∈ {7, 39, 52, 56} on one 7-isogeny 4-cycle 52–7–39–56–52; y² = x³ + x + 16 (j = 7) is one 7-step away.
- `tournament.py`: 2000 candidates (0–6 random 7-isogeny steps, then u-rescaling, exact transport of G, Q),
  12 paired seeds, factor-base (x < 20, ≤ 2-summand decompositions), BSGS and r = 8 rho solvers.
  Cost unit: group ops + w·(lookups + mod-41 LA mul-adds), w ∈ {0, 0.1, 1}. Every solve returns 17.
- `analyze.py` → `summary.json`; `holdout.py` → `holdout.json` (winners re-scored on 12 fresh seeds);
  `figs.py` → `tournament.png/pdf`. Full output: `results.json.gz` (gunzip to `results.json` first).

Result (w = 1): factor-base candidate means min 149.00 / max 1034.33 / avg 342.36 (1000) and 344.19 (2000);
min and max do not move when the pool doubles (161 of 164 models already present). The winner is the
freely rescaled start curve (u = 69), not an isogeny; its advantage holds on fresh seeds (148.67), while
the rho "winner" regresses to the pool mean (139.83 → 154.50). BSGS is constant at 19.5. The screenshot's
absolute counts use a different unit and are not reproduced. Run: `python3 tournament.py && python3
analyze.py && python3 holdout.py && python3 figs.py` (needs matplotlib).
