The first locked control returned SAT but `replay_model` reported
`invalid_leaf_support`: its raw first leaf decoded as zero. The model
decoder in the imported `build_m5.py` reads only positive literal IDs.
The rectangle leaf map uses negated literals when the affine offset and
a basis vector share a normal-basis coordinate. The original protocol,
runner, control, solver stdout/stderr, compressed XCNF, and failed
receipt in this directory preserve the exact attempt. The corrected
runner expands negative literal truth values before independent point
replay. The initial 16,384-seed domain check passed, then was moved
here because its hashes refer to the original runner and protocol.
