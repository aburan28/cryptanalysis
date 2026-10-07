# Fresh single-use test of fixed hybrid τ digit alphabet

The retrospective 32-case training receipt in
`hybrid-training-result.json` selected **mask 31** before this
holdout source or its inputs were created. Its allowed width-four
seeds are `{0,1,2,3,4,5,6,7}`; seed 8 is replaced by the
corresponding width-three digit. This test uses the fixed mask as a
single-pass recoder. It compares with pure width-three (mask 0) and
pure width-four (mask 63) on 64 new secp256k1 base/scalar pairs,
with one scalar per base. The SHA-256 label in the source fixes inputs
without inspecting their outcomes.

For each arm and base, construct only the dependency closure of seed
points actually used by that arm's digit stream. Check every
constructed point against the independent Sage group expression.
Batch-normalize only used constructed points with one inversion and
prepare their three-element `ω` orbits. Evaluate with explicit
paired-τ and mixed-addition formulas. Check exact ring-digit
reconstruction and each complete output against Sage's `kP`.

The frozen cost model is the one in `HYBRID_SUBSET_PROTOCOL.md`:
the source-specific Jacobian chain costs by seed index, one field
multiplication per used seed for its orbit, `(6m−3)M+mS+1I` to
normalize `m>0` used constructed points, `6M+4S` per cheap paired
stride, `4M+2S` per ordinary τ, and `8M+3S` per mixed addition after
the first free insertion. Save `M`, `S`, and `I` separately, plus
`M+S` under `S=M`. The inversion cost is **not** zero; because all
ordinary arms use one inversion, their `M+S` difference is a
controlled symbolic comparison, not a full wall-time result.

The result must preserve every input, short representative, digit
length/weight, seed set and dependency closure, point digest, output,
source hash, and correctness. A failed assertion aborts the script
without a partial failure row; this is a limitation of the
prototype. No CPU speedup, side-channel security, or academic
novelty claim follows from this run. The recoding is variable-time
and is intended only for public scalars until separately reviewed.

Freeze this protocol and `hybrid_holdout.py` before deriving inputs.
Save the checked Sage runtime receipt, then execute:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/hybrid-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/hybrid_holdout.py
```
