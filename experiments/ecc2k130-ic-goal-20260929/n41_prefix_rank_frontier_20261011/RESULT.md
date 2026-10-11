# Universal consistency of the first linear relaxation after fixing all eight N41 source masks

**For the frozen 498-equation N41 quadratic joint system, its first degree-two linear relaxation is consistent for every assignment of the eight six-bit source masks.** The exact free-monomial coefficient matrix has rank 413. Its 85 independent row dependencies cancel the complete mask-dependent right-hand side as polynomial identities. The source masks do not appear in any mixed mask/free monomial, so the coefficient matrix is constant across all `2^48` assignments. This proves that fixing more source pairs cannot make this particular linear relaxation reject a prefix; a multiplication-aware constraint is required for early pruning.

## Exact system and certificate

The system is the archived selected raw-target branch of the ordinary N41 public point `Q=(1458168294740,1672312028033)` on `EC1N41Ckb1h7d5e80d3c4d0`. Its first 48 Boolean variables are the eight W6 source masks; the other 372 are the joint point-decomposition variables. Every equation has degree at most two. After treating each monomial in the free variables as an independent binary variable, there are **10,212** appearing free monomials and **zero** monomials containing both a mask and a free variable.

Write the relaxed equations as `A u = b(m)`, with 498 rows, fixed-mask vector `m`, and independently lifted free-monomial vector `u`. The producer computed `rank(A)=413`, plus 85 independent row combinations annihilating `A`. For each combination, it XORed the full fixed-mask polynomials and obtained the zero polynomial, including the constant term. Hence `b(m)` belongs to the column space of `A` for every `m`. The [certificate](universal_proof.json) retains the 85 exact row combinations and source hashes. The [independent checked-Sage verifier](universal_sage_audit.json) reparsed the frozen polynomial file, used the opposite pivot direction, checked rank 413 and independent dependency rank 85, verified every polynomial cancellation, and checked a 64-column GF(2) minor.

## Sampled prefix and group controls

The [frozen protocol](protocol.json) includes all 978 distinct-column first-pair mask choices, plus 128 independently sampled valid prefixes and the known positive for each deeper prefix length. Sampling chose valid masks uniformly per slot and rejected repeated folded columns. The [screen](result.json) took 10.986 seconds of local exploratory wall time and recorded 38,551,552 bytes peak self RSS.

| Fixed source pairs | Fixed bits | Prefixes checked | Consistent relaxations | Matrix rank |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 12 | 978 | 978 | 413 |
| 2 | 24 | 129 | 129 | 413 |
| 3 | 36 | 129 | 129 | 413 |
| 4 | 48 | 129 | 129 | 413 |

The [independent Sage point replay](sage_replay.json) checked the first five complete prefixes. The known positive admits a signed eight-point sum equal to `Q`; four independently sampled full prefixes do not, although each passes the relaxation at rank 413. These are exact false-positive controls for the relaxation. The [terminal audit](audit.json) binds the frozen polynomial system, base input, sample law, producer, two Sage checks, and runtime receipt. This is a method-selection result with `candidate_id: null`.

## Next method test

Keep the source-mask/free-product identities coupled when eliminating the 413 linear directions. A useful next gate must derive a compact nonlinear constraint that rejects whole two-pair source families while their masks remain variable, then test it on this same unpinned N41 public point under the one-worker, 120-second, 4-GiB envelope. An N131 ordinary query follows only after a source-bound full-work projection for 600 seconds and 4 GiB.

Reproduce with `python3 -B experiments/ecc2k130-ic-goal-20260929/n41_prefix_rank_frontier_20261011/run.py prepare`, then `run`, `universal_proof.py`, checked `/Volumes/SSD990/cryptanalysis/sage -python` for `verify_sage.py` and `universal_verify_sage.py`, and `audit.py` in a fresh copy of this write-once directory. Save `/Volumes/SSD990/cryptanalysis/sage --runtime-info` before either Sage job.
