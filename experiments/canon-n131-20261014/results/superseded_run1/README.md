# Superseded first run (kept, not used)

`instructions.json` is the cachegrind table of the first full run. Two rows are
wrong because of how the instrument was attached, not because of the arms:

- `gap_scan` (1,324 / 1,291 Ir per word): its per-gap `consider` closure was
  compiled out of line, so the `canon131_gap_scan` symbol's self Ir left out
  every rotate-and-compare (`asm_check.json` of that build: 4 `call`s).
- `fmul` (14 Ir): the exported wrapper could not inline the
  `#[target_feature]` multiply, so only the wrapper was counted.

The fix makes `consider` an `#[inline(always)]` function (as `consider_gap` is
at n = 83), puts the target feature on `fmul131_clmul` itself, and makes
`run.py` refuse to count Ir for any arm whose code contains a `call`. The
other arms were leaf functions in both builds; their rows are reproduced
exactly by the second run (see the README's determinism check).
