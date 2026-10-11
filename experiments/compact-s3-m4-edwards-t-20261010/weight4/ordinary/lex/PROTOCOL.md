# Q20261010175900: sorted-leaf ordinary N53 t-S3 formula

Take the exact Q20261010174500 public point, factor base, and archived
three-link formula. Add `leaf[0] <= leaf[1] <= leaf[2] <= leaf[3]` in
the normal-basis coordinate integer order. Four-point addition is
commutative, and the balanced S3 links can represent every permutation,
so each decomposition has a sorted representative. The comparator uses
native XOR equality bits and CNF prefix implications; it adds no field
multiplication gates. This is an exact symmetry reduction.

Freeze source, input, binary, and flags before building or solving. First
validate the comparator against all 3-bit input pairs by SAT. Build the
augmented formula from the archived XCNF, then use one CryptoMiniSat thread,
seed zero, 100,000 conflicts, and a 300-second external wall cap. Audit any
model against the serialized XCNF and the exact factor base and signed
group law. The conflict budget matches an early checkpoint in the unsorted
cell; wall timings on this shared host remain exploratory.

Run `python3 experiment.py freeze`, `python3 experiment.py check`,
`python3 experiment.py build`, `python3 experiment.py solve`, and
`python3 audit.py`. Outputs refuse overwrite. A solver limit or wall cap
without a model is `BOUNDED_UNKNOWN`.
