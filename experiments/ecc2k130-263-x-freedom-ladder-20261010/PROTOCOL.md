# Fixed-witness x-coordinate freedom ladder for Q1420

The source/descendant `wz_only` W24 circuits have verified fixed six-distinct-leaf
positive controls. They also have `BOUNDED_UNKNOWN` full `x0` and `x5` releases
at a 120-second solver cap. This experiment fixes the same six selectors, all
six inverse-coordinate words, the other five x words, four finite projective
S3 intermediates, and the positive raw target lift. It releases only selected
bits of one leaf x word. The measured outcome is the width-dependent solver
status, not an ordinary-query relation yield or a timing speedup.

`source.json` pins the parent commit, archives, named-input maps, solver binary,
two curves, leaves 0 and 5, and widths 1/4/8/16/32/64/96/131. At width k,
the released bit set is the first k positions of `(53*j) mod 131`; 53 is
coprime to 131, so width 131 releases the entire coordinate. The order
spreads released bits across the polynomial basis. Each cell receives one
CryptoMiniSat 5.14.7 native-XOR attempt, one thread, a 20,000-conflict cap,
30-second internal and 40-second external wall caps, and a sampled 4-GiB
RSS cap. Run order is leaf-major, width-major, source then descendant. The
host lacks the isolated-benchmark receipt, so wall/CPU values are exploratory;
statuses and correctness are the comparison.

Freeze and commit `source.json`, `PROTOCOL.md`, and the runner/auditor before
generating cell inputs. Then run `python3 -B .../ladder.py freeze`, commit
`runs/R1/cells.json` and all unit deltas, and only then launch
`python3 -B .../ladder.py all`. Retain raw stdout/stderr, exit state, guards,
sampled RSS, process CPU, conflicts, and complete formula/input hashes for
all 32 cells. The auditor independently reconstructs unit deltas and full
XCNFs from the parent gzip archives. For SAT, it replays every CNF clause and
native XOR, decodes the six leaves, and checks signed group addition to the
exact raw target. Capped cells stay `BOUNDED_UNKNOWN`; a failed producer is a
separate failure, and unexpected UNSAT contradicts the archived satisfying
witness. Existing parent positive, negative, full x, and z-release cells are
context only; no timing comparison across different caps is promoted.

The decision is conditional on the recorded frontier. If narrow x releases
already consume the conflict cap, test a functional x-equation encoding or
field-linear cut at the leaf. If SAT persists until a wider release, freeze
that width and test a partial-assignment/cube policy on ordinary held-out
queries. Either follow-up must charge all failures and verify decompositions,
rank, and eventual target recovery before becoming an IC result. The equal-B
six-policy and primary one-target gates remain unchanged.
