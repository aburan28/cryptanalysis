# Power-basis Karatsuba for the N83 five-summand S₃ formula

The exact power-basis Karatsuba circuit reduces the width-16 S₃ formula from
63,329 to 12,138 AND gates and from 258,716 to 105,143 CNF clauses on the
same public target and complete factor base. Its locked five-point control
returns SAT and passes independent Sage group replay. The ordinary Q53 run
reached the frozen five-million-conflict cap after 443.4 solver seconds, with
stage status `bounded_unknown`.

The field is the type-II optimal normal basis representation of
GF(2^83) on `y² + xy = x³ + 1`; the prime subgroup has order
2,417,851,639,230,796,216,685,689. The shifted width-16 base has
**B = 5,419,568 distinct usable subgroup points before folding** and
**K = 32,648 signed-Frobenius columns**. The workload ID is
`df4396f4d8fc`. [The protocol](protocol.json) fixes its public point,
base and canonical-x hashes, raw cofactor preimage choice zero, one
CryptoMiniSat thread, 5,000,000 conflicts, 600-second wall cap and 4 GiB
sampled solver RSS stop. The target-generation scalar is represented only
by its SHA-256 commitment in the protocol and is not read by this solver.

## Circuit comparison

| Formula, same width-16 base and target slice | AND gates | CNF clauses | Native XOR rows | Variables |
| --- | ---: | ---: | ---: | ---: |
| Q50 direct ONB products | 63,329 | 258,716 | 1,593 | 65,584 |
| Q53 power-basis Karatsuba | 12,138 | 105,143 | 62,870 | 75,670 |

The multiplier expresses each ONB input in powers of `gamma_1`, applies
recursive characteristic-two Karatsuba to the coefficient polynomials,
and reduces monomials 0 through 164 back into the same power basis. All
intermediate S₃ coordinates stay in that basis; the five leaves and fixed
target are converted once. The lower AND and CNF counts trade for many
short XOR rows, so gate reduction alone does not measure decomposition
throughput.

On the exploratory local host, Q53 reached 5,000,001 reported conflicts
in 443.401 solver seconds and 231,686,144 bytes sampled peak solver RSS.
CryptoMiniSat returned `INDETERMINATE` at the conflict cap; its wrapper
labels exit code 15 `solver_failure`, while the stage record correctly
retains `bounded_unknown`. Q50 reached its 600-second external wall cap;
the last printed progress line reported about 2.074 million conflicts.
These are different stopping boundaries and local timing lacks a host
isolation receipt. The Q53 target-dependent PDP interval was 443.676
seconds, with the exclusive phase costs in
[width16_ordinary.json](width16_ordinary.json). The raw solver output,
stderr and compressed XCNF are hash-bound by that receipt.

The [topology screen](topology_shapes.json) held the base, fixed target and
leaf policy constant. Balanced, left-deep, right-deep, reordered-pair and
target-as-third-input chains each produced the Q50 gate and clause counts;
placing the target as the first input produced 70,218 AND gates and
279,383 clauses. The Karatsuba comparison changes the field multiplier,
not the factor-base policy. The earlier Q52 invocation stopped before
solver launch due to a recursive wrapper call. Its original
[protocol](protocol_Q2026101252_predriver.json) and
[failure receipt](predriver_failure.json) remain separate from Q53.

## Verification and proof map

The inverse 83 by 83 change-of-basis matrix is computed by elimination;
the producer checks 32 fixed-seed field products against independent ONB
multiplication. The locked control pins all five leaf and intermediate
coordinates, returns SAT in 0.208 solver seconds and passes exact
signed/cofactor group replay. [Independent Sage replay](sage_relation_replay.json)
checks that relation through a separately constructed polynomial field and
curve. [verify.py](verify.py) checks source, solver, base, control, protocol,
phase and compressed-formula hashes.

The generic characteristic-two cross-term identity used at every
Karatsuba split is `N83Karatsuba.cross_term_char_two` in
[Karatsuba.lean](Karatsuba.lean). Lean 4 v4.34.1 checks it with axioms
`propext` and `Quot.sound`; [lean-build.txt](lean-build.txt) retains
`#print axioms`. The full 83-coefficient circuit, change-of-basis map and
S₃-to-curve bridge are covered by executable checks above and remain open
as Lean formalization obligations. `lean4checker` was unavailable on this
host.

Use the checked repository Sage launcher for local work:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info
python3 experiments/n83-geometric-m5-topology16-20261012/verify.py
```

The Sage replay receipt is already frozen in this directory. The
producers and replay verifier refuse to overwrite terminal evidence;
reproduction of a new run should use a fresh output directory with this
protocol and the frozen public inputs.
