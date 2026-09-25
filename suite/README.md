# cryptanalysis-suite

The attack library and command-line tools, in Rust: 148 attack modules
against symmetric ciphers, hash functions, elliptic-curve and finite-field
discrete logarithms, signature nonces, lattices and the NIST post-quantum
schemes, plus the primitives they target.  It is the cryptanalysis suite
of the [crypto](https://github.com/aburan28/crypto) study repository,
moved here and put under this repository's checks.

Where the C library in the parent directory is one generic-group interface
with a handful of fast, measured solvers over 64-bit groups, the suite is
the wide end: many attacks, arbitrary precision (`num-bigint`), and
Markdown reports.  The two do not depend on each other.

```sh
cargo build --release                 # ca-suite, ca-ic, ca-icx, ca-curves, ca-koblitz-pdp-prepare
cargo test --release                  # 2761 unit + 65 integration tests, ~6 min on 4 cores
./target/release/ca-suite --help
```

Requirements: Rust 1.87 or newer (declared in `Cargo.toml`, checked in CI).
AVX-512 target features are stable only from Rust 1.89, so `build.rs` compiles
the AVX-512 kernels (Koblitz scan, `F_p` tower F4, `GF(2)` elimination, the
wide FES walk) only on such a toolchain; older ones take the AVX2 and scalar
paths, which compute the same values.
`ca-ic fixed` additionally drives the Python engine in `python/indexcalc/`
with `python3` (standard library only; `python-sat` or `pycryptosat` only
for its SAT solver).

## Command line

`ca-suite` has one subcommand per tool.

```sh
$ ca-suite list-ciphers
Registered ciphers:
  toyspn-1r              16-bit SPN: 4 × 4-bit S-boxes + PRESENT-style bit permutation block=2B rounds=1
  ...
  aes-4r                 AES-128 with reduced round count block=16B rounds=4

# Every applicable attack against a registered cipher, as a Markdown report
$ ca-suite auto --cipher toyspn-2r
# Auto-cryptanalysis: `toyspn-2r`
...
## Boomerang distinguisher
- **right quartets**: 16352 / 65536
- **empirical (pq)²**: 2.4951e-1
- **random baseline**: 1.5259e-5
- **distinguishes from random (10×)**: ✓

# One attack at a time
$ ca-suite sbox --cipher aes-2r
$ ca-suite boomerang --cipher toyspn-3r --pairs 65536
$ ca-suite rectangle --cipher toyspn-1r --pool 2048
$ ca-suite aes-related-key --key-bits 256

# Hash attacks: length extension, birthday, Joux multicollision, differential bias
$ ca-suite hash-auto --hash md5
$ ca-suite length-extension --hash sha1 --secret-len 16 --message-hex ... --suffix-hex ... --digest-hex ...

# ML-KEM / ML-DSA: lattice estimates against the NIST floors, and the
# implementation attacks that recover real keys
$ ca-suite mlwe margins
instance                             cat  NIST floor  gates+tour    margin      +d4f  cheapest attack
ML-KEM-512                             1       143.0       137.1      -5.9     -12.1  dual-matzov (unfiltered)
ML-KEM-768                             3       207.0       211.3      +4.3     -10.2  primal-usvp
...
$ ca-suite mlwe kem-pco --param 768 --oracle pc      # full key from decapsulation leakage
$ ca-suite mlwe dsa-leak --per-poly 64               # s1 from four ML-DSA-65 signatures
$ ca-suite mlwe dsa-fault --fault all

# Collaborative Pollard rho: one ECDLP across many machines, each
# check-in self-verifying
$ ca-suite rho-collab init --curve demo-32 --secret 0x1234567 --out job.json
$ ca-suite rho-collab work --job job.json --node alice --threads 2 --listen 0.0.0.0:7000
$ ca-suite rho-collab work --job job.json --node bob --peer alice:7000
$ ca-suite rho-collab status --job job.json --peer alice:7000 --json

# The visual demos and the falsifiable-hypothesis research bench
$ ca-suite isogeny volcano --curve toy-b --ell 2 --depth 4
$ ca-suite isogeny experiment --bits 10 --trials 2 --ell-list 2,3 --rho-cap 16384
$ ca-suite isogeny secp256k1
$ ca-suite visual-all --target pollard-rho
$ ca-suite aes-visual-demo --demo dfa
$ ca-suite bench
```

`ca-ic` inspects curves and runs bounded, reproducible index-calculus
experiments with known answers: on binary Koblitz curves, and with
`ca-ic prime` on prime-field curves by type — generic (NIST P-192 … P-521),
`j = 0` Koblitz-style (secp256k1) and `j = 1728` — over a scaled-down curve of
the named curve's shape, a batch of targets against rho, both per target and
as a batch that shares distinguished points; see
[docs/ic/README.md](docs/ic/README.md).

```sh
$ ca-ic list
$ ca-ic ecc2k-130                                   # inspection only
$ ca-ic p224                                        # inspection only
$ ca-ic run --degree 11 --curve-a 1 --known-log 53 --solver enumerate --json
$ ca-ic compare --degree 7 --curve-a 1 --samples 3 --holdout 2 --json
$ ca-ic fixed --params docs/ic/params/k0n9-fixed.json --dir runs/k0n9 --attempts 256 --json
$ ca-ic prime --curve secp256k1 --bits 28 --targets 64  # j = 0: |Aut| = 6 orbits, a batch vs rho
$ ca-ic boundary --quick                            # every IC variant vs the generic floor and a counted rho
$ ca-ic swap --cells 13:3 --pairs 16                # is a solver priced the same on R and R - P + Q?
$ ca-ic bench --sweep docs/ic/sweeps/solver-engines.json   # plug-in pipeline configurations, compared
$ ca-ic descent --families K --cells 11:6:2        # degree a Weil-descent system reaches vs semi-regular
$ ca-ic corpus --degree 15 --dimension 5 --dir corpus/   # Semaev S4 corpus (Magma, DIMACS+XOR, CNF, ANF)
$ ca-ic rho --koblitz-degrees 23,31 --runs 4       # the counted Pollard-rho references, paired
```

`ca-icx` runs index calculus across every standardized curve: the curve
catalog (`curve_catalog`), the engine that classifies each curve into an
attack regime and prices it (`ic_engine`), and a verified run on the curve
or a same-family analogue (`ic_run`, through the configurable pipeline in
`ic_framework`); see [docs/ic/FRAMEWORK.md](docs/ic/FRAMEWORK.md).

```sh
$ ca-icx list --family koblitz
$ ca-icx inspect secp256k1
$ ca-icx estimate sect163k1
$ ca-icx run secp256k1 --json                       # on a same-family analogue inside the envelope
```

`ca-curves` lists the challenge corpus in [`../challenges/ecc/`](../challenges/ecc/README.md)
and can emit a collaborative Pollard-rho job for a prime-field curve:

```sh
$ ca-curves list --family binary-koblitz --max-bits 64
$ ca-curves show fp-j0-b32
$ ca-curves rho-job fp-j0-b32 --seed 1 > job.json
$ ca-suite rho-collab work --job job.json --node local --threads 2
```

`ca-koblitz-pdp-prepare` plans and prepares the sealed-oracle / blind-bundle
Phase-A point-decomposition artifact sets.

## What is in the library

`cryptanalysis_suite::cryptanalysis` is the suite; the other modules are
the targets and the arithmetic they stand on.

### Analytical primitives

| module | what it gives you |
|---|---|
| `sbox` | DDT, LAT, BCT (Cid et al. 2018), DLCT (Bar-On et al. 2019), truncated DDT, differential / linear uniformity, nonlinearity, algebraic degree, boomerang uniformity |
| `boolean` | Walsh-Hadamard transform, ANF, algebraic degree |
| `avalanche` | full avalanche matrix, SAC, BIC over any `fn(&[u8]) -> Vec<u8>` |
| `statistical` | chi-squared, monobit, runs tests |
| `lattice` | LLL and BKZ reduction |
| `sat` | a CDCL solver with native XOR clauses, used by the Semaev and Koblitz oracles |
| `groebner_f4`, `f4_fp`, `pq_groebner_f2`, `pq_xl`, `crossbred`, `mq_fes`, `mq_monica` | Gröbner / XL / Crossbred / FES engines over `F_2` and small `F_p` |
| `pq_sparse_la`, `pq_wiedemann`, `koblitz_sparse_la` | sparse linear algebra: structured filtering, (block) Wiedemann |

### Symmetric-cipher attacks

| module | attack |
|---|---|
| `boomerang` | generic boomerang distinguisher, rectangle and sandwich attacks, branch-and-bound trail search |
| `aes::{reduced, square, differential, linear, impossible, mixture, boomerang, yoyo, mitm, small_scale, algebraic, milp, biclique, related_key, truncated_diff, higher_order, dfa, slide, zero_correlation, cache_timing, dpa, quantum_grover, visualize}` | the reduced-round AES-128 attack catalogue, from the Square attack to DFA and cache-timing, each against the crate's own AES |
| `md5_differential`, `md5_chosen_prefix`, `md5_hashclash_ffi`, `sha1_differential`, `hash_attacks` | Wang-style MD5 collisions, chosen-prefix collisions (optionally through HashClash), SHA-1 differentials, length extension, Joux multicollisions |
| `cipher_registry`, `auto_attack`, `research_bench` | the named-cipher catalogue, the auto-attack runner, and the falsifiable-hypothesis bench with log-log exponent fits |

### Discrete-log and ECDLP attacks

| module | attack |
|---|---|
| `pollard_rho`, `preprocessing_rho`, `ml_rho_walks`, `aut_folded_rho`, `bsgs_fast`, `ecdlp_variants` | Pollard rho (multi-shard, distinguished points), Bernstein-Lange precomputation, learned partition walks, automorphism-folded rho on CM curves, BSGS and Gaudry-Schost variants |
| `ec_challenges` | the elliptic-curve challenge corpus ([challenges/elliptic](../challenges/elliptic/README.md)): prime, binary, ternary and odd-extension fields from a few bits to 768, Koblitz and subfield curves, j = 0 / 1728 / generic, supersingular, anomalous, twist pairs, and multi-level isogeny volcanoes, each tagged with the solver that should be fastest |
| `pollard_collab` | the collaborative rho: indexed work units, self-verifying DP check-ins, CRDT merge, mailbox / TCP gossip / cairn transports ([design](docs/POLLARD_COLLAB_DESIGN.md)) |
| `pohlig_hellman`, `cheon_attack`, `ecm`, `shor`, `quantum_estimator` | Pohlig-Hellman, Cheon's strong-DH attack, ECM factoring, Shor's order finding, quantum resource estimates |
| `prime_orbit_index_calculus`, `ec_index_calculus_curves` | index calculus on prime-field curves by type — generic, `j = 0` (secp256k1) and `j = 1728` — with factor bases of whole automorphism orbits, certified scaled-down curves, exact logarithms, descent, and a batched rho baseline |
| `ec_index_calculus`, `ec_index_calculus_j0`, `residual_walk`, `gaudry_cubic`, `semaev_*`, `symmetrized_semaev`, `diem_descent`, `descent_*`, `degree_reduction*`, `coordinate_*` | Semaev index calculus on prime-field curves and `E(F_{p^3})`, residual walks, Diem descent, and the summation-polynomial machinery they share |
| `koblitz_*`, `binary_semaev*`, `wdsat_oracle`, `polynomial_reuse`, `algebra_cache` | Frobenius-invariant factor bases on binary Koblitz curves, the F4 / SAT / WDSat decomposition oracles, relation collection and the sparse solve |
| `ghs_descent`, `ghs_full_attack`, `binary_isogeny`, `ec_trapdoor`, `hyperelliptic_index_calculus`, `coleman_integration` | Weil descent (GHS / Hess) from `E(F_{2^n})` to a hyperelliptic Jacobian and index calculus there |
| `canonical_lift`, `cm_canonical_lift`, `nonanom_formal_log`, `mazur_tate_sigma`, `ai_schoof`, `modular_polynomial`, `hilbert_class_poly`, `isogeny_class_search`, `isogeny_degree_search`, `j0_twists`, `quasi_subfield` | the Smart attack on anomalous curves and its p-adic relatives, Schoof, modular and class polynomials, isogeny-class and twist enumeration |
| `mov_attack`, `eds_*`, `petit_quisquater`, `pkm_criterion`, `fght_snfs`, `legacy_curve_attacks`, `invalid_curve_attack` | MOV / Frey-Rück pairing transfers, elliptic divisibility sequences, the Petit-Quisquater and PKM criteria, a toy trapdoored-prime SNFS, invalid-curve attacks |

### Signature, nonce and structural attacks

| module | attack |
|---|---|
| `hnp_ecdsa`, `multi_key_hnp`, `bleichenbacher`, `cga_hnc`, `b_seed_profile`, `orbit_homology` | hidden-number-problem key recovery from biased nonces (LLL / BKZ), multi-key HNP, Bleichenbacher's bias attack and its relatives |
| `ecdsa_audit`, `signature_corpus` | transcript audits: nonce reuse, weak RNGs, bias scores, corpus-level findings |
| `p256_attacks`, `p256_structural`, `p256_isogeny_cover`, `p256_speculation`, `solinas_correlations` | P-256-specific structure and the speculation that was tested and did not survive |
| `mlwe::{params, cost, primal, dual, hybrid, sieve, report}`, `ml_kem_pco`, `ml_dsa_leakage`, `ml_dsa_fault` | ML-KEM / ML-DSA: primal / dual / hybrid estimators under five SVP cost models, working sieves and BKZ, and the decapsulation-oracle, mask-leakage and fault attacks against the crate's real FIPS 203 / 204 implementations ([write-up](docs/mlwe-cryptanalysis.md)) |
| `tls12_kdf`, `tls13_kdf`, `signal_ratchet` | key-schedule analyses |

[docs/ECDLP_ATTACK_MATRIX.md](docs/ECDLP_ATTACK_MATRIX.md) is the
attack-by-curve-family applicability matrix.

### Integer factorisation

`cryptanalysis::factoring` attacks RSA's hardness assumption directly.
Every entry point takes an options struct with size-dependent defaults,
returns a `serde::Serialize` report (factors, per-stage timings, factor-base
and matrix sizes, relations, dependencies tried), never prints, and never
reports a factor it has not verified by multiplication.

| module | what it does |
|---|---|
| `factoring::nfs` | the **number field sieve**: shared core (rational and algebraic factor bases, quadratic characters, segmented line sieve with resieving and one large prime per side, singleton filtering, structured Gaussian elimination + Method-of-Four-Russians dense GF(2) solve, exact algebraic square root by Newton lifting from an inert prime, verified `δ² = Γ`), with two front ends: `gnfs` (base-m polynomial selection with leading-coefficient search, rotation and Murphy α; degree 3 up to 65 digits) and `snfs` (`n \| c·rᵉ + s` or an explicit `(f, m)`; reducible and Aurifeuillian polynomials split `n` directly) |
| `factoring::qs` | self-initialising quadratic sieve (Knuth–Schroeppel multiplier, Gray-code polynomial switching, single large prime), sharing the NFS linear algebra |
| `factoring::pm1`, `factoring::rho_factor` | Pollard p − 1 (stage 1 + prime-by-prime stage 2), Williams p + 1, Pollard–Brent rho |
| `factoring::rsa_attacks` | Fermat (close primes), Wiener (small `d`), Håstad broadcast, common modulus, small-`e` root, batch GCD over a product/remainder tree, `(n, e, d) → p, q` |
| `factoring::auto` | `factor(n, &options)`: trial division → perfect power → BPSW → rho → p − 1 → ECM (`cryptanalysis::ecm`) → SNFS (if a form is given) → SIQS / GNFS, recursing on cofactors; prime powers with exponents and the method that isolated each |

Measured with `cargo run --release --example nfs_demo` on one core (one
thread) of a shared, loaded 4-core machine, so treat them as upper bounds;
every row is a verified factorisation:

| method | n | digits | total s | sieve / linalg / sqrt s | relations (full + partial) | dense matrix |
|---|---|---|---|---|---|---|
| SIQS | semiprime | 40 / 50 / 55 / 60 | 0.2 / 1.2 / 3.2 / 16.2 | — | 3128 + 5805 at 60 | 912 × 848 at 60 |
| GNFS | semiprime | 40 | 0.8 | 0.3 / 0.2 / 0.0 | 4067 + 37250 | 1440 × 1406 |
| GNFS | semiprime | 45 | 3.1 | 1.5 / 0.4 / 0.4 | 5607 + 76570 | 2757 × 2722 |
| GNFS | semiprime | 50 | 8.9 | 6.8 / 0.8 / 0.5 | 7812 + 113846 | 4513 × 4481 |
| GNFS | semiprime | 55 | 17.7 | 14.1 / 1.9 / 0.7 | 13775 + 225289 | 7695 × 7647 |
| GNFS | semiprime (`--big`, separate runs) | 58 / 59 | ≈ 60–75 / ≈ 100–140 | sieve-bound | | |
| SNFS | `2^227 − 1`, `x⁴ − 2` | 69 | 6.8 | 5.4 / 0.8 / 0.4 | 5733 + 128468 | 4157 × 4124 |
| SNFS | `(2^239 + 1)/3`, `x⁴ + 2` | 72 | 9.8 | 8.4 / 0.9 / 0.3 | 7985 + 158967 | 5167 × 5134 |
| SNFS | `(3^163 − 1)/2`, `x⁴ − 3` | 78 | 22.4 | 19.8 / 1.9 / 0.4 | 12825 + 244866 | 7821 × 7787 |

`--threads N` parallelises the sieves (rayon) across `N` workers.

What this is not.  It is an educational implementation with production
habits, not msieve / YAFU / CADO-NFS: no lattice sieve, no bucket sieve,
no Kleinjung polynomial selection or full root optimisation, no double
large primes, no Block Lanczos, no Montgomery/Nguyen square root.  In this
code the QS beats the GNFS at every size either can reach (the NFS only
wins from ~100 digits with those missing pieces), so `auto` sends
composites up to 100 digits to the QS unless `prefer_nfs` is set; GNFS
above ~60 digits and SNFS above difficulty ~80 take many minutes to hours.
The algebraic square root needs a prime modulo which `f` is irreducible,
so polynomials whose Galois group has no `d`-cycle (e.g. `x⁴ + 1`) are
rejected rather than handled by CRT.  Primality is BPSW (proven below
`2⁶⁴`, probable above; the reports say which).

### The targets

`symmetric` (AES, ChaCha20-Poly1305, Serpent, Threefish, SM4, Kuznyechik,
Magma and some forty more), `hash` (SHA-1/2/3, MD4, MD5, RIPEMD-160, SM3,
Streebog, BLAKE2/3, Skein, Whirlpool), `ecc` and `binary_ecc` (prime- and
binary-field curves, ECDSA, Ed25519/Ed448, X25519), `prime_hyperelliptic`,
`asymmetric` (RSA, Paillier, ElGamal), `pqc` (ML-KEM, ML-DSA, SLH-DSA,
FN-DSA, SQIsign, MAYO, NTRU, McEliece, BIKE, HQC and the other NIST
round-2 candidates), `kdf`, `ecc_safety`, `ct_bignum`, `utils`,
`visualize`.

**None of this is constant-time or audited.**  The primitives are here to be
attacked and the attacks are here to measure; nothing in this crate protects
anything.  Use `aws-lc-rs`, `ring` or RustCrypto for that.

## What the numbers mean

An attack module's headline is an operation count in a stated unit against a
stated boundary (rho at `S = ops / sqrt(n) ≈ 1.3` for the ECDLP threads, the
NIST category floors for the lattice estimators), never a wall-clock time.
The research notes that derive each boundary, freeze each measurement and
classify each change stay in the upstream repository; the tool docs here
link to them where a number needs its provenance.

## Layout

```
src/lib.rs                 the crate: cryptanalysis + the modules it targets
src/cryptanalysis/         the suite (148 modules)
src/isogeny/               CM / class-group / Vélu / volcano research module (ca-suite isogeny)
src/main.rs, src/cli_mlwe.rs   ca-suite
src/bin/ic.rs, src/bin/ic/     ca-ic
src/bin/icx.rs             ca-icx
src/bin/koblitz_pdp_prepare.rs ca-koblitz-pdp-prepare
tests/                     integration tests (ca-ic and ca-icx end to end, the PARI curve audit, LLL probes)
tests/data/                the PARI/GP audit template
examples/                  148 runnable demos and measurement harnesses
python/indexcalc/          the stdlib-only index-calculus engine behind `ca-ic fixed`
fixtures/                  the two frozen contracts the F4 and Weil-factor tests read
docs/                      tool guides: ic, ML-KEM/ML-DSA cryptanalysis, collaborative rho, attack matrix
deny.toml                  cargo-deny: licences, advisories, sources, duplicate versions
```

## Checks

The `suite` workflow gates every change on: `cargo fmt --check`;
`cargo clippy --all-targets -- -D warnings` (three lints are allowed in
`Cargo.toml`, each with its reason; do not widen the list); `cargo test
--release`; `cargo doc` with `-D warnings`; a build and test on the declared
MSRV; and `cargo deny check`.  From the repository root, `make suite` runs
the same set.

The tests that take minutes rather than seconds are `#[ignore]`d with a
reason string (`cargo test --release -- --ignored` runs them); the bench
demos print their Markdown with `--nocapture`.

## What was not migrated, and why

The `crypto` repository also holds `research/` (every note and frozen
experiment directory), the per-stage Koblitz workflows, the ECC2K-130 GPU
fleet (`ecc2k130/`, `gpu/`) and its HDL (`hdl/`), the Sage / PARI
companions, the cryptopals solutions, the zero-knowledge, TLS 1.3 and
BLS12-381 modules, and the speed-oriented PQC benchmarks.  Those are either
research records, or primitives no attack here reaches, or a parallel
campaign this repository already has production versions of (`cuda/`,
`fpga/`, `orchestrator/`); they stay upstream.
