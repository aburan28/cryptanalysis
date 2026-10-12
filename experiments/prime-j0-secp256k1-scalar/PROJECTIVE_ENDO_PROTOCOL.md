# Inversionless endomorphism-assisted one-use scalar format

Freeze this protocol and `projective_endo.py` before deriving 64 fresh
one-use secp256k1 base/scalar pairs. Use the checked repository Sage
launcher and save `--runtime-info` before the run. Both arms use the same
short `a+bτ` representative, width-four digits, optimized nine-point
endomorphism seed chain, precomputed unit orbits, and paired-τ evaluator.
One arm retains all eight constructed seeds in Jacobian coordinates; the
other batch-normalizes all eight with one inversion. Every seed and output
must independently match Sage. Save every raw input, cost, output, source
hash, and any failure; do not overwrite prior results.

The source-count boundary starts from an affine input base point. The
optimized projective seed chain costs `42M+32S`, and orbit preparation
costs `9M`. Batch-normalizing eight seeds adds `45M+8S+1I` to the
affine arm. Online use charges every paired/single τ step and general or
mixed addition, with the first insertion from the identity free. The
common final output inversion and replay are kept separate and cancel
in the paired comparison. The projective arm has no *preparation*
inversion; it still needs its output inversion for affine output.

Report the paired threshold

`I_break_even = (projective M+S) − (affine M+S)`

for one preparation inversion, along with the distribution over cases.
Do not turn it into a wall-time claim without a native 256-bit kernel,
complete recoding/setup/output timing, and the host-isolation receipt.
The current Rust `SecpFieldElement::inv` source performs 256 field
multiplications and 512 squarings in its 256-round ladder, but this is
only an operation-count diagnostic for that implementation and not an
empirical inversion calibration. The published width-four method and
Montgomery batch inversion are prior art; academic novelty is unproved.
