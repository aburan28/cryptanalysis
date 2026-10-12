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

The design receipt `design.json` binds the input, plan, screen, and atlas
sources; `design-rows.jsonl` preserves every scalar's terminal state and
paired source cost. `TerminalUnit.lean`, `DigitCover.lean`, and
`OrbitAtlas.lean` prove the seven-state terminal theorem, complete scalar
reconstruction, and orbit digit transport for every integer scalar.

The next gate is an independent holdout generated only after this design
snapshot is committed, followed by native implementation and complete
point replay. The source count is a model of ordinary addition paths;
recoding, table construction, memory access, exceptional paths, and field
kernel latency need complete-operation measurement on an isolated host.
