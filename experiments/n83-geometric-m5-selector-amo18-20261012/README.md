# Sequential Frobenius selectors in the N83 width-18 S₃ circuit

Replacing four 83-way pairwise one-hot selector encodings with exact
sequential at-most-one encodings removes **12,632 CNF clauses** from the
same width-18 Karatsuba formula: 105,251 to 92,619. The field-product
circuit stays at 12,174 AND gates and 62,937 native XOR rows. A locked
five-point control returns SAT and passes independent Sage group replay.

The [Q56 protocol](protocol.json) fixes the same public point,
`df4396f4d8fc` workload, shifted width-18 base and raw target choice
zero as [Q54](../n83-geometric-m5-karatsuba18-20261012/README.md).
The base contains **B = 21,714,958 distinct usable subgroup points
before folding** and **K = 130,813 signed-Frobenius columns**. The only
formula variable is the selector CNF. Every selector has one at-least-one
clause; the candidate uses a prefix counter for at-most-one instead of
all pairwise negative clauses. [The shape screen](shape_screen.json)
also retains exhaustive existential-equivalence checks for selector
widths 2 through 6 and 32 fixed-seed field-product checks.

| Frozen choice-zero formula | Pairwise | Sequential |
| --- | ---: | ---: |
| AND gates | 12,174 | 12,174 |
| CNF clauses | 105,251 | 92,619 |
| CNF literal occurrences | 278,111 | 252,847 |
| Native XOR rows | 62,937 | 62,937 |
| Variables | 75,783 | 76,111 |

The [ABBA pilot](pilot_result.json) ran each formula twice in the order
pairwise, sequential, sequential, pairwise, with one CryptoMiniSat thread,
60-second wall limit, 4 GiB sampled RSS stop and 300,000-conflict cap
per arm. The pairwise XCNF raw SHA-256 exactly matches Q54's archived
choice-zero formula. All four arms printed `INDETERMINATE` after
300,002 reported conflicts; the wrapper retained exit-code 15 as
`solver_failure`, and the pilot status is `bounded_unknown`.

| Arm | Encoding | Solver seconds | Reported conflicts |
| ---: | --- | ---: | ---: |
| 0 | pairwise | 17.026 | 300,002 |
| 1 | sequential | 16.987 | 300,002 |
| 2 | sequential | 16.986 | 300,002 |
| 3 | pairwise | 15.193 | 300,002 |

The two sequential arms did not show a solver-time gain against the
bracketing pairwise arms, so this pilot does not promote the encoding
to a longer ordinary search. These are exploratory local-host stage
times, with no host-isolation receipt. The formula-size reduction is an
exact implementation result; target relation yield and complete-pipeline
online timing remain separate measurements.

[verify.py](verify.py) checks all frozen sources, base and public-target
hashes, the locked control, both compressed formula inputs and four raw
solver outputs. [Independent Sage replay](sage_relation_replay.json)
checks the locked group relation through a separately constructed
polynomial field and curve. The checked Sage launcher recorded
[runtime identity](sage_runtime_info.json) before the pilot.

Run the read-only receipt check from the repository root:

```sh
python3 experiments/n83-geometric-m5-selector-amo18-20261012/verify.py
```

The producers refuse to overwrite terminal evidence; use a fresh output
directory to reproduce a new pilot.
