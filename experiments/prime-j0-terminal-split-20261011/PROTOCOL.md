# Cost-aware representative with a split terminal

The fixed-generator secp256k1 evaluator keeps the 64 MiB radix-1024 cover
and its existing 149-radius terminal table. For each public scalar, enumerate
the four lattice representatives at the nearest-plane cell corners. Recode
each through the same twelve full-window rows. A terminal pair inside the
existing norm disk uses one table entry. For a terminal outside that disk,
try the four coordinate-wise floor/ceiling halves and retain a two-entry
split only when both parts are in the existing disk and sum to the terminal.
This changes the scalar selection and online work, not the stored tables.

Choose the option with the lowest declared point-work proxy: 11 per mixed
addition, 14 per full bucket merge, 6 for an active tau-one bucket, 10 for
an active tau-two bucket, and one per grouped unit rotation. Break ties by
fewer terminal entries, the original nearest-norm representative, its norm,
and its coordinates. The original path is always available. The proxy is a
selection rule and an operation diagnostic; it excludes four recodings,
candidate lookup, memory traffic, and final inversion. It is not a CPU-time
estimate.

Freeze `replay.py`, `verify.py`, `make_inputs.py`, this protocol, and the
inherited cover in a source commit before drawing the final 4,096-scalar
panel. `make_inputs.py` must check modular disjointness from the existing
panels, including the budget-optimal cover's final panel, and record the
frozen source hashes. Replay the original and selected paths on the same
scalars. Preserve every option and its terminal split in the certificate.
An independent verifier must check the input law, each class decoding,
terminal table code, integer reconstruction, subgroup congruence, selection
rule, and paired operation totals. Check boundary scalars and a separate
binary point path as correctness controls. If the operation saving survives,
integrate a native evaluator and replay the same frozen panel before making
any runtime claim. CPU timing requires the repository's host-isolation gate.

The initial 256-scalar diagnostic used already-seen inputs. It found 110
active tau-two buckets for the original path and 14 for this selection under
the point-work proxy, with 89 selected paths using two terminal points.
That diagnostic only motivated this prospective protocol.
