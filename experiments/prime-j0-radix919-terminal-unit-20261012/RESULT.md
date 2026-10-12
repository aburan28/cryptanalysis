# Radix-919 terminal-unit design result

Thirteen radix-919 unit-orbit windows plus a seven-state terminal correction
reduce the canonical affine table by **96,823 points (5.025%)** against
radix 943. The full-residue atlas has 140,761 canonical digits across
844,561 residues, giving 1,829,893 window points and one canonical
terminal-correction point. The point array is **117,113,216 bytes** at
64 bytes per point, versus 123,309,888 bytes for radix 943.

On the frozen 4,096-scalar design panel, 211 scalars required a terminal
unit correction. The remaining 3,885 terminated after thirteen windows.
Every recoding reconstructed its exact initial Eisenstein pair. The
radix-919 source model used 486,343 ordinary-path field products versus
484,163 for format 174 on the same panel, an increase of 2,180 (0.450%).
The summed modeled product depth decreased from 199,382 to 199,373.

| Frozen design metric | Radix 943, format 174 | Radix 919 with terminal correction |
| --- | ---: | ---: |
| Scalar cases | 4,096 | 4,096 |
| Canonical point entries | 1,926,717 | 1,829,894 |
| Point bytes at 64 per entry | 123,309,888 | 117,113,216 |
| Selected affine terms | 53,248 | 53,459 |
| Gauge rotations | 9,027 | 9,097 |
| Modeled field products | 484,163 | 486,343 |
| Summed modeled depth | 199,382 | 199,373 |

After the design snapshot was committed as `9543d45cc`, a new 512-scalar
holdout was generated from seed `20261012919`. All **512/512** outputs from
the radix-919 decomposition matched independently generated secp256k1
points after each selected term was separately constructed as a point and
the terms were summed with an affine group law. Thirty holdout scalars used
the terminal correction. The holdout source model used **60,840 products**
versus **60,518** for radix 943, an increase of 322 (0.532%).

| Frozen holdout metric | Radix 943 | Radix 919 with terminal correction |
| --- | ---: | ---: |
| Scalar and point cases | 512 | 512 |
| Selected affine terms | 6,656 | 6,686 |
| Gauge rotations | 1,126 | 1,148 |
| Modeled field products | 60,518 | 60,840 |
| Summed modeled depth | 24,939 | 24,926 |
| Independently replayed point outputs | — | 512/512 |

The design receipt `design.json` binds the input, plan, screen, and atlas
sources; `design-rows.jsonl` preserves every scalar's terminal state and
paired source cost. `TerminalUnit.lean`, `DigitCover.lean`, and
`OrbitAtlas.lean` prove the seven-state terminal theorem, complete scalar
reconstruction, and orbit digit transport for every integer scalar.

The next gate is a native implementation of the recoder, table, and XYZZ
evaluation, followed by complete-operation measurement. The source count
is a model of ordinary addition paths;
recoding, table construction, memory access, exceptional paths, and field
kernel latency need complete-operation measurement on an isolated host.
