# ECC2K-130 W24 normal-basis barrel gate

**Decision: admit this representation to a bounded planted unknown-witness
m5 solver test, without promoting it to an IC candidate or a speedup claim.**
R2 passed the frozen correctness panel. The first SHA-derived normal element
(counter 0) has full rank 131. All 120 archived field words round-tripped
through independently reconstructed polynomial and normal bases. All 1,200
frozen exponent rotations matched direct GF(2^131) Frobenius in checked
Sage. All 56 planted W24 seed/exponent pairs reconstructed the parent field
words. The verifier rejected a wrong rotation and a wrong normal-element
counter with nonzero exits and no accepted output. The accepted status is
`PASS_INDEPENDENT_SAGE_NORMAL_BASIS_REPLAY` in
[`runs/R2/independent-sage.json`](runs/R2/independent-sage.json).

The circuit front end is explicit: 24 W24 seed bits map into 131 normal
coordinates; eight 131-bit conditional rotations select exponent `0..130`;
the result maps back to polynomial coordinates for later equations. The
full 131-column polynomial-to-normal and normal-to-polynomial matrices,
the 24-column restricted seed map, and all three matrix digests are in
[`runs/R2/result.json`](runs/R2/result.json). These are direct, row-wise
linear-circuit counts, without cross-output XOR sharing or synthesis:

| Exact structural quantity | Per leaf | Five leaves |
| --- | ---: | ---: |
| W24 seed → normal XORs | 1,417 | 7,085 |
| Eight-layer conditional-rotation muxes | 1,048 | 5,240 |
| Normal → polynomial XORs | 8,406 | 42,030 |
| Mux equivalent ANDs | 1,048 | 5,240 |
| Mux equivalent XORs | 2,096 | 10,480 |
| All direct XORs including mux equivalents | 11,919 | 59,595 |

The equivalent mux decomposition is `out = a XOR ((a XOR b) AND select)`.
The gate ledger does **not** count the exponent `≤130` constraint, curve
rationality, Semaev equations, Booleanization, solver work, relation
verification, matrix construction, target descent or scalar recovery. Its
large output conversion may dominate the front end; the measured cost of a
complete solver is unknown. The host was not isolated, so the producer's
124.090 ms and independent Sage replay's 2,224.605 ms are exploratory
reproduction diagnostics, not CPU speedup evidence. Peak RSS was
24,707,072 B and 262,832,128 B respectively.

R2's raw result SHA-256 is
`7b45cc0a5c6b1299bccf4b79c514fb26cffebdd51ab21be6ec2c8a8dfbf83b54`.
The checked launcher runtime receipt SHA-256 is
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The result binds the frozen config and source hashes, including the parent
R1 result `1bfc3cecc51309926f4c801133b9b96ff1587d69d0a80c4460079fda52c83cdd`.
Protocol commit `36e638a0f4402e4a3baa9632319f715632a3d2de`, initial
implementation commit `8b3408ec11470e55bfe7c36b7902efeacc2e7cad`,
and full-matrix correction commit `ed2a303a` were pushed to
[PR #366](https://github.com/aburan28/cryptanalysis/pull/366) before
their respective frozen runs. The [SHA-256 manifest](SHA256SUMS) checks
the protocol, code, parent inputs and all run receipts.

[`runs/R1/STATUS.md`](runs/R1/STATUS.md) preserves the first passing but
schema-incomplete run: it omitted the full polynomial-to-normal matrix
required by the protocol. R1 is not the accepted gate and its timing is
not compared to R2 as a performance experiment.

This still has **zero ordinary PDP queries**. The 64 negative inputs are
uniformly derived field words, not natural group-sum queries; their lack
of W24-closure membership is not a yield estimate. No verified relation,
novel rank, final logarithm or rho result exists here. `candidate_id`,
natural yield, and target-online costs remain `null`. The parent
[seed gate](../ecc2k130-orbit-closed-w24-seed-20261006/RESULT.md) also
explains why arbitrary subgroup-point membership needs `[4]` preimage and
torsion handling; this R2 concerns only the field-coordinate front end.

The next decision is a paired, bounded **unknown-witness** m5 experiment:
attach this exact front end to a complete Boolean/Semaev system, enforce
exponent range inside the solver, and recover hidden W24 masks and exponents
from planted group sums. Freeze the same planted instances and limits for a
one-hot Frobenius selector baseline. Record satisfiable/timeout/OOM rates,
proof or replay of each witness, clauses/variables, peak RSS and exclusive
solve cost, preserving zero-yield cells. If either path solves enough
unknown-witness controls, freeze a separate ordinary-query panel to measure
natural relation yield and novel rank. Only then compare it with original
W24/m6 and W28/m5 on a complete IC workload.

To reproduce R2, run the unit tests and producer with fresh output paths,
then record the accepted runtime and replay through the checked launcher:

```sh
python3 -m unittest discover -s experiments/ecc2k130-w24-normal-barrel-20261006 -p test_normal_barrel.py
shasum -a 256 -c experiments/ecc2k130-w24-normal-barrel-20261006/SHA256SUMS
python3 experiments/ecc2k130-w24-normal-barrel-20261006/run.py --out /tmp/w24-barrel-result.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /tmp/w24-barrel-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python "$PWD/experiments/ecc2k130-w24-normal-barrel-20261006/verify_sage.py" --result /tmp/w24-barrel-result.json --runtime-info /tmp/w24-barrel-runtime.json --out /tmp/w24-barrel-verification.json
```

Fresh wall-time fields and result hashes will vary; exact matrices and
control decisions should agree. For mutation replay, run
`check_mutations.py` with `--result`, `--runtime-info`, and a fresh `--out`
path. Its subprocesses always use the checked repository Sage launcher.
