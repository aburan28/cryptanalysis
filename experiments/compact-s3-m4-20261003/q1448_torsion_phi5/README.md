# Q1448: torsion-symmetrized five-input SAT stage

Q1448 tests a way to constrain four sparse leaves and a public target
**without fixing pair-intermediate coordinates first**. It implements the
characteristic-two, two-torsion invariant polynomial of Faugère, Huot,
Joux, Renault, and Vitse, [*Symmetrized Summation Polynomials*, Section
5.1](https://www.iacr.org/archive/eurocrypt2014/84410158/84410158.pdf),
for the exact curve `y²+xy=x³+1`. The expression is evaluated as a compact
field circuit; no expanded ordinary `S5` polynomial is materialized.

For the five x coordinates (four leaves and one raw target preimage), set
`u_i = 1/(x_i+1)`, `Y_i = u_i²+u_i`, `e = Σu_i`, and let `s_j` be the j-th
elementary symmetric polynomial in the `Y_i`. With the paper's `γ=1` and
`λ=0`, the circuit sets

`e⁸ + e⁶s₅ + e⁴s₄² + e²s₃²s₅ + s₃⁴ + e²s₅³ + s₂²s₅² + s₅⁴ + s₅³ = 0`.

Each raw leaf x retains its exact normal-basis Hamming-weight constraint.
The Boolean formula introduces `u_i` and enforces `u_i(x_i+1)=1`, so the
change of coordinate does not silently alter the factor base. It selects
among **all** archived raw target preimages after transforming their x
coordinates. Exceptional `x=1` targets are rejected during construction;
none occur in the frozen N53/N83 workloads. A returned model must still
pass independent rational-lift, cofactor/subgroup, distinct-column, sign,
and public-target replay.

The exact inputs are Q1438's N53 W≤4 curve
`EC1N53Ckb1hf77aab617904` with `B=324,042`, folded `K=3,057`, and set
digest `9e12afb51aaf2bbf47640554ce88b3653903375c33489ce8b1e07abe6a649cae`;
and N83 W≤6 curve `EC1N83Ckb1h876c2921cb64` with `B=408,131,750`,
folded `K=2,458,625`, and set digest
`c1ee6d1064935976fc0d3e479f895fe4832722b5991ba148a6d6cb003b76330d`.
The ordinary public targets and workload IDs are exactly Q1438's. Q1448
is a point-decomposition stage `PDP4phi5`, defined in `AGENTS.md`, with
`candidate_id: null` and `isogeny: "none"`; no complete `IC1` method is
named.

## Frozen gates and results

The [pre-run controls](validation.json) independently reconstruct the
archived N53 ordinary witness and an N83 planted witness with exact curve
arithmetic, verify the polynomial vanishes, and solve the fully pinned
Boolean encodings. Both controls are SAT. The first frozen protocol failed
only during a Python import preflight, before any ordinary formula or
solver began. Its [failure record](failed_preflight.json) and
[original protocol](protocol_v1_failed.json) are retained. The corrected
[protocol](protocol.json) was committed before either ordinary run.

| Ordinary degree | CNF variables / clauses | Formula build | CaDiCaL solver | Conflicts / decisions | Peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 184,858 / 695,821 | 0.606 s | 60.115 s, censored | 193,838 / 589,000 | 349,306,880 bytes | 0 |
| N83 | 451,997 / 1,650,799 | 1.492 s | 60.205 s, censored | 37,648 / 298,099 | 583,565,312 bytes | 0 |

The 60-second cap is per native solver process, with a one-million-conflict
cap and 75-second outer safeguard. The raw CaDiCaL output also records
281,232,849 N53 and 112,789,382 N83 propagations. Both cells exited at
the wall cap without a SAT model or a relation. CPU times on this host are
exploratory without an isolation receipt. The runner's inclusive stage
interval is 63.475 s for N53 and 104.432 s for N83; it includes research
CNF archive compression, which accounts for much of the extra N83 time.
That interval is not a clean one-target online IC time or a solver-speed
ratio. Preserve it as instrumentation-inclusive accounting alongside the
exclusive formula-build and solver intervals.

The [independent archive audit](verification.json) regenerates both CNFs,
checks the exact curve/base/target identities, source and binary hashes,
and frozen receipts. A successful ordinary N83 decomposition has **not**
been measured. The pinned controls establish correctness of this encoding
on known witnesses; they do not estimate natural relation yield. No
N53-to-N83 successful-solve growth rate, cost per useful row, or complete
N131 `2^x` follows. The challenge gate remains closed.

## Reproduction

All local Sage work uses the checked repository launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1448_torsion_phi5/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1448_torsion_phi5/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The ordinary runner refuses to overwrite either archived cell. The
method's next useful gate is a solver that exploits the invariant field
structure rather than only bit-blasting it: measure unpinned ordinary
N53/N83 relations and retain failed queries, rank, operations, memory, and
the full phase ledger. Merely changing a Boolean branching order without
verified ordinary progress is insufficient for a N131 work claim.
