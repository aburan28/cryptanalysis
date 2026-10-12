# Canonical radix-943 Pareto scalar format

Format 174 combines thirteen radix-943 unit-orbit table selections with
canonical Solinas field arithmetic and a Pareto gauge-aware XYZZ addition
tree for fixed-base secp256k1 scalar multiplication. On a separately
generated 512-scalar holdout, all 512 points matched an independent Python
Jacobian implementation. Its source model used **60,522 field products**
on ordinary addition paths, versus **65,786** for format 173 on the same
scalars: **5,264 fewer (8.002%)**. Each holdout scalar saved 9–12 modeled
products. The larger retained table, constants, atlas, and plans occupy
**127,488,664 bytes (121.58 MiB)**.

| Frozen scalar panel | Format 173: U14 Pareto | Format 174: radix-943 Pareto |
| --- | ---: | ---: |
| Design scalars | 4,096 | 4,096 |
| Design active terms | 57,343 | 53,248 |
| Design gauge rotations | 10,082 | 9,027 |
| Design modeled field products | 526,168 | 484,163 |
| Design summed modeled product depth | 200,505 | 199,382 |
| Holdout scalars | 512 | 512 |
| Holdout active terms | 7,168 | 6,656 |
| Holdout gauge rotations | 1,274 | 1,130 |
| Holdout modeled field products | 65,786 | 60,522 |
| Holdout summed modeled product depth | 25,062 | 24,913 |
| Retained table, atlas, constants, plans | 64,342,768 B | 127,488,664 B |

The source model charges each tree with `10n−14` ordinary-path field
products for `n` selected affine terms, plus one per gauge rotation. It
does not model exceptional formula branches, recoding, table construction
or lookup, affine recovery, or field-kernel latency. The 4,096-case native
test recounts candidate design totals from selected digits and plans.
`screen.py` independently reconstructs the digit atlas, the U14 recoder,
and the frozen plan table for both panels. Holdout operation counts are
from that source-model replay; the holdout CLI validates output points,
not native product counters. Therefore the figures compare modeled work,
not complete-operation wall time.

The protocol and implementation were committed as `1ed06551d` before
holdout generation. `holdout.py` then generated 512 distinct 256-bit draws
reduced modulo the subgroup order from seed `20261012174` and computed their points
through separate Jacobian double-and-add code. Its scalar-byte digest is
`e5f36b7ccf764a0daa6f920cc828f24bd2a073cfebcf701a526084674f203ece`.
The release CLI for both formats matched every holdout scalar and expected
point. Format 174 also passed the inherited independent 129-case fixture.
The design test compared all 4,096 outputs to format 173 and the first 128
to independent native binary multiplication. Raw outputs and the verifier
receipts are retained here; `receipt.json` binds their hashes to the
frozen source and binary.

`Recoding.lean` checks exact reconstruction of both signed radix
coordinates from thirteen steps with zero terminal state. The inherited
`GaugeTree.lean` and `ParetoCost.lean` check the group-sum and ordinary-path
tree-cost implications. `PROOF.md` records hypotheses and the remaining
covering-radius and Rust-refinement proof obligations.

The next performance gate is a paired complete-operation format-173/174
run with prepared tables and a strict host-isolation receipt. The currently
available RunPod container fails that preflight, so this experiment makes
no CPU wall-time ranking. The implementation is variable-time and intended
for public scalars; using secret scalars requires a constant-time table
selection and recoding design.
