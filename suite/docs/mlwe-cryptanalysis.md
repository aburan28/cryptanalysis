# Cryptanalysis of ML-KEM and ML-DSA

What is implemented, what it says, and which numbers not to trust.

Code: [`src/cryptanalysis/mlwe/`](../src/cryptanalysis/mlwe/),
[`src/cryptanalysis/ml_kem_pco.rs`](../src/cryptanalysis/ml_kem_pco.rs),
[`src/cryptanalysis/ml_dsa_leakage.rs`](../src/cryptanalysis/ml_dsa_leakage.rs),
[`src/cryptanalysis/ml_dsa_fault.rs`](../src/cryptanalysis/ml_dsa_fault.rs).
CLI: `ca-suite mlwe --help`.

## The short version

The lattice attacks are estimators; the implementation attacks actually run and
actually recover keys. That asymmetry is the finding, not a limitation of the
code:

| attack | scale | result |
|---|---|---|
| primal uSVP, dual, MATZOV-style dual, hybrids | estimates at real parameters | `2^127`–`2^320` |
| ML-KEM decapsulation-leakage key recovery | **runs, real ML-KEM** | full key in **8 queries** (message leakage) or **3072** (one-bit oracle) |
| ML-DSA mask-leakage key recovery | **runs, real ML-DSA-65** | full `s1` from **4 signatures**, then a forgery the library's own verifier accepts |
| ML-DSA fault attacks | **runs, real ML-DSA-65** | full `s1` from **1** faulted signature |

## Part 1 — the lattice estimators

### What sets the level

Everything reduces to two questions, and [`cost.rs`](../src/cryptanalysis/mlwe/cost.rs)
keeps them apart because conflating them is how estimates go wrong:

1. **What does BKZ-β achieve?** A basis profile. Stable, well-supported.
   Implemented three ways: the closed-form `δ(β)` fit, the q-ary "z-shape", and
   a Gaussian-heuristic BKZ simulator.
2. **What does BKZ-β cost?** An SVP model. This is where every published
   disagreement lives, and the spread across the models in this file is more
   than `2^40`.

| model | one SVP call | note |
|---|---|---|
| `core-svp-classical` | `2^{0.292β}` | ADPS16 convention; Kyber's and Dilithium's headline numbers |
| `core-svp-quantum` | `2^{0.265β}` | **the entire known quantum advantage against these schemes** |
| `gate-count` | `2^{0.292β + 16.4}` | round-3 convention; the one comparable to NIST's floors |
| `sieve-memory` | `2^{0.349β}` | charges for touching a `2^{0.292β}` database |
| `enumeration` | `2^{0.187 β log₂β − 1.019β + 16.1}` | polynomial memory; loses to sieving above β ≈ 300 |

Nothing picks a default silently, and every estimate carries its model's label.

### Attacks

* **primal uSVP** — the baseline both schemes were designed against. Two
  independent conditions (the ADPS16 closed form and the BKZ simulator) agree to
  within a few block sizes.
* **dual** — in the normal form `{(x, y) : Aᵗx ≡ y}`, because the textbook kernel
  form is *useless* here: ML-KEM's public key gives exactly `n` samples for `n`
  unknowns, so the kernel degenerates to `q·Z^m`.
* **MATZOV-style dual** — the three-way split (lattice / FFT / enumeration) with
  modulus switching. This is the variant behind the widely-quoted claim that
  Kyber-512 sits a few bits below its category-1 requirement, and we reproduce
  that sign.
* **hybrids** — and the answer is that they do not help here. See below.

### Reproduced results

`ca-suite mlwe margins`:

```
instance                             cat  NIST floor  gates+tour    margin      +d4f  cheapest attack
ML-KEM-512                             1       143.0       137.1      -5.9     -12.1  dual-matzov (unfiltered)
ML-KEM-768                             3       207.0       211.3      +4.3     -10.2  primal-usvp
ML-KEM-1024                            5       272.0       284.6     +12.6      -6.0  primal-usvp
ML-DSA-44 (key recovery, MLWE)         1       143.0       147.5      +4.5      -1.9  dual-matzov (unfiltered)
ML-DSA-65 (key recovery, MLWE)         3       207.0       208.5      +1.5     -12.9  dual-matzov (unfiltered)
ML-DSA-87 (key recovery, MLWE)         5       272.0       282.8     +10.8      -7.7  primal-usvp
```

ML-KEM-512 coming out under its floor is the known result, not a surprise, and
it is why deployment guidance points at ML-KEM-768. The primal core-SVP numbers
land within 25 bits of the Kyber submission's 118 / 183 / 256, which a test
asserts.

**The `+d4f` column is the less trustworthy one**, and the reason is in the code:
the `+16.4` gate constant was measured for a sieve that already exploits
dimensions for free, so subtracting `d4f` on top of it plausibly double-counts
the same saving. A negative there is a statement about stacked models, not a
break.

### Diagnostics: the part that matters

A dual estimate on its own is not a security claim. Every dual result carries
[`DualDiagnostics`](../src/cryptanalysis/mlwe/dual.rs):

* **Ducas–Pulles contradictory regime** — flags an estimate that consumes more
  short dual vectors than the lattice contains at the length it assumes. Left to
  optimise freely, the MATZOV grid walks straight into this; a test asserts it
  does, because if it ever stopped doing so the cost model would have changed.
* **Provable regime** — whether each sample is informative enough that
  concentration bounds apply without the independence heuristic.
* A test asserts the two are **never both true**, which is Pouly–Shen's headline
  disjointness result, checkable here.

Both are our operationalisations of those papers' criteria, not transcriptions
of their theorems, and the doc comments say so.

### Two negative results worth recording

**Hybrid primal attacks do not help at these parameters.** Getting this right
took separating the cost model from the success condition:

* Under the **uSVP** condition the reduction is paid once *per guess*, so the
  exponents add. A coordinate costs `H ≥ 1.4` bits and buys about `0.29` bits of
  block size. Optimum: guess nothing.
* Under the **Babai decoding** condition the reduction is paid once in total —
  the amortisation the hybrid exists for — but the condition is far stronger
  (*every* Gram–Schmidt norm above `2σ`, not just the first) and the block size
  it demands more than eats the saving.

Charging "reduce once" while requiring only uSVP produces an apparent 30–55 bit
hybrid win on ML-KEM. It is not real. Wunderer's *Revisiting the hybrid attack*
is a paper about versions of this error. The published 2–15 bit gains are on the
**dual** side, where short vectors are reused across guesses for free.

**ML-DSA's forgery (MSIS) side comes out weak** — `2^106` for ML-DSA-44 — and
that is expected: `ζ' = max(2(γ₁−β), 4γ₂+2)` is enormous, and a short SIS
solution is not yet a signature. What protects ML-DSA against forgery is the
challenge hash, not the SIS bound. This is why nobody quotes the SIS number as
the security level.

### Sieves that run

[`sieve.rs`](../src/cryptanalysis/mlwe/sieve.rs) implements the Gauss sieve
(Micciancio–Voulgaris), the Nguyen–Vidick sieve, and a bucketed
near-neighbour sieve in the shape of BDGL16, plus a progressive-BKZ driver.
They run in dimensions 4–40, which is nowhere near ML-KEM's 500–2000 — that gap
is why the estimators exist. What they do establish is measured rather than
asserted: exact agreement with exhaustive search in small dimension, and a
~38× reduction in pair comparisons from bucketing, which is the finite-dimension
shadow of the `2^{0.292d}` exponent.

```
$ ca-suite mlwe sieve --algo bucketed --dim 20 --buckets 40
  shortest before:  |v|^2 = 3365
  shortest after:   |v|^2 = 40
  buckets: 40   pairs: 18957 bucketed vs 718800 all-pairs   speedup: 37.9x
```

One bug found along the way is worth recording because it is the kind that hides:
the lattice sampler retried whenever size-reduction collapsed a sample to zero,
and for some reduced bases *most* small combinations collapse, so the retry loop
did not terminate. It now keeps the unreduced combination instead.

## Part 2 — the attacks that work

### ML-KEM: chosen-ciphertext key recovery from decapsulation leakage

[`ml_kem_pco.rs`](../src/cryptanalysis/ml_kem_pco.rs). ML-KEM is IND-CCA2 secure
and nothing here contradicts that. What it attacks is the gap the FO transform
leaves in *implementations*: decapsulation decrypts the attacker's ciphertext
with the long-term key before deciding to reject it. The decision is constant
time and the output reveals nothing — but the decryption happened.

Nothing constrains the attacker to a well-formed ciphertext. Set `u₀ = U·X⁰`,
`uᵢ = 0`, `v = V·Xʲ` and decryption collapses to a threshold test on one secret
coefficient. A handful of `(U, V)` pairs separates all `2η+1` values.

```
$ ca-suite mlwe kem-pco --param 512 --oracle full
  queries: 8     recovered correctly: 512/512     decapsulates: true
$ ca-suite mlwe kem-pco --param 768 --oracle pc
  queries: 3072  recovered correctly: 768/768     decapsulates: true
```

The success criterion is not a coefficient count: the recovered key is used to
**decapsulate honest ciphertexts it never saw**, and the derived shared secret is
compared against the real one.

### ML-DSA: key recovery from mask leakage

[`ml_dsa_leakage.rs`](../src/cryptanalysis/ml_dsa_leakage.rs). `z = y + c·s1`
with `z` and `c` both public, so `y` is the only thing between an observer and
`s1`. When whole coefficients of `y` leak, each one is a linear equation over
`Z_q`; 256 per component and it is Gaussian elimination, no lattice and no
failure probability.

```
$ ca-suite mlwe dsa-leak --per-poly 64
  signatures observed: 4    recovered correctly: 1280/1280    forgery verified: true
```

**`s1` alone is a universal forgery** — no `s2`, no `t0`. Verification only ever
involves the combination `t0 − s2`, and that equals `A·s1 − t1·2^d`, which is
computable from `s1` and the public key. So the attack stops at `s1`, forges, and
the library's own `ml_dsa_65_verify` accepts.

The partial-bit variant is a hidden-number problem and is solved by LLL at a
dimension LLL can reach, with an honest note that the real `n = 256` instance
needs BKZ at a serious block size (fplll or G6K, not this crate's LLL).

### ML-DSA: fault attacks on the rejection loop

[`ml_dsa_fault.rs`](../src/cryptanalysis/ml_dsa_fault.rs). Three faults, all
against the real signer:

| fault | signatures | note |
|---|---|---|
| `y = 0` | 1 | clears every rejection check — `‖c·s1‖∞ ≤ τη = 196`, far inside `γ₁ − β` |
| same `y` on two messages | 2 | `z − z' = (c − c')·s1`; the mask never has to be known |
| one polynomial of `y` zeroed | ℓ | one component of `s1` per fault |

All three end in a verified forgery.

**Hedging does not help.** Hedged mode mixes fresh randomness into `ρ''` so a bad
RNG cannot repeat `y`. That defends against randomness failure. It does nothing
against a fault applied after `y` is derived, and nothing against a probe — the
published ~300-trace key recovery works in hedged mode.

## Part 3 — how this bears on the rest of the library

The `pqc::fast::*` modules are **not constant-time**, by design: they optimise
throughput, with data-dependent branches and table lookups. `docs/pqc-speed.md`
says so. Part 2 above is what that costs. They are a benchmarking and
cryptanalysis vehicle, not a deployment candidate.

## Honesty ledger

* The refined cost models involve fitted constants and optimisation choices
  their authors' own code makes. Where we simplify, the doc comment at that line
  says so. `dual_matzov` implements MATZOV's *structure* with our accounting; it
  will not reproduce their table to the bit.
* The Ducas–Pulles and Pouly–Shen regime tests are our operationalisations,
  chosen so the disjointness their papers establish is checkable here.
* The BKZ simulator omits Chen–Nguyen's HKZ head correction. That tail does not
  enter the primal or dual conditions; it would matter for a tail-reading attack.
* The `l∞ → l2` conversion for ML-DSA's SIS bound uses the standard `·√m`
  convention, which is lossy.
* No attack here uses the ring or module structure. None is known that does; if
  one appears, that flattening is the assumption it breaks.

## Commands

```
ca-suite mlwe estimate --scheme ml-kem-768 --model gate-count --tours [--d4f] [--simulate]
ca-suite mlwe table [--model M]        # every attack x every set x every model
ca-suite mlwe margins                  # against the NIST category floors
ca-suite mlwe sis                      # the ML-DSA forgery side
ca-suite mlwe sieve --algo gauss|nv|bucketed --dim N
ca-suite mlwe scaling --dims 10,12,14  # measured sieve growth
ca-suite mlwe bkz --dim N --beta B     # progressive BKZ, measured profile
ca-suite mlwe kem-pco --param 512|768|1024 --oracle full|pc
ca-suite mlwe dsa-leak --per-poly 64
ca-suite mlwe dsa-partial --n 8 --m 22 --bits 12
ca-suite mlwe dsa-fault --fault all|zero|reuse|partial
ca-suite mlwe budget                   # mask-leakage budgets vs published figures
```

## References

* Alkim, Ducas, Pöppelmann, Schwabe, *Post-quantum key exchange — a New Hope*, USENIX 2016.
* Becker, Ducas, Gama, Laarhoven, *New directions in nearest neighbor searching*, SODA 2016.
* Chen and Nguyen, *BKZ 2.0*, ASIACRYPT 2011.
* Ducas, *Shortest vector from lattice sieving: a few dimensions for free*, EUROCRYPT 2018.
* MATZOV, *Report on the security of LWE*, 2022.
* Ducas and Pulles, *Does the dual-sieve attack on LWE even work?*, 2023.
* Pouly and Shen, *Provable dual attacks on learning with errors*, EUROCRYPT 2024.
* Wunderer, *Revisiting the hybrid attack*, 2016.
* Micciancio and Voulgaris, *Faster exponential time algorithms for the shortest vector problem*, SODA 2010.
* Ravi, Roy, Chattopadhyay, Bhasin, *Generic side-channel attacks on CCA-secure lattice-based PKE and KEMs*, TCHES 2020.
* Ueno, Xagawa, Tanaka, Ito, Takahashi, Homma, *Curse of re-encryption*, TCHES 2022.
* Bruinderink and Pessl, *Differential fault attacks on deterministic lattice signatures*, TCHES 2018.
* Key recovery from randomness leakage in ML-DSA, *Journal of Cryptology* 2026.
