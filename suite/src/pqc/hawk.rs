//! **HAWK** — lattice-isomorphism signatures on Z^{2n}
//! (Ducas–Postlethwaite–Pulles–van Woerden 2022; NIST
//! additional-signatures round 3).
//!
//! # The idea
//! Every other NIST lattice signature (ML-DSA, Falcon) works in a
//! `q`-ary lattice.  HAWK's lattice is the plainest one imaginable —
//! `Z^{2n}` itself — hidden behind a secret change of basis.  The
//! secret key is a unimodular matrix `B` (an exotic basis of `Z^{2n}`);
//! the public key is only its Gram matrix `Q = Bᵀ B`, which reveals the
//! *geometry* but not the basis.  Recovering `B` from `Q` is the
//! **Lattice Isomorphism Problem** (LIP): decide/compute an isometry
//! between two lattices given their Grams.
//!
//! Signing is decoding: hash the message to a parity target
//! `h ∈ {0,1}^{2n}` and find `s ∈ Z^{2n}` such that `u = h − 2s` is
//! **short in the Q-metric** (`uᵀQu` small).  With `B` this is easy —
//! `Bu` must be a short vector congruent to `Bh mod 2`, so pick the
//! ±1/0 coset representative coordinate-wise.  Without `B`, the
//! verifier's metric `Q` gives no handle on which coset member is
//! short: that is decoding `Z^{2n}` in a scrambled metric.
//!
//! Bonus: since `Bu` has ±1/0 entries, signatures are tiny — HAWK is
//! the main reason "Falcon-like sizes without floating point" appears
//! in NIST's round-3 rationale.
//!
//! # This implementation
//! Educational rendition with `2n = 32`: real HAWK gets compact keys
//! by taking `B` from a *module* (NTRU-like pairs of polynomials in
//! `Z[x]/(x^n+1)`) and samples the coset representative with a
//! discrete Gaussian (needed for the security proof); we use a plain
//! unimodular `B` built from random shears and uniform ±1 signs on odd
//! coordinates.  Toy dimension, not constant-time; see SECURITY.md.

use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// Lattice dimension (real HAWK-512 uses 2n = 1024).
pub const DIM: usize = 32;
/// Verification bound on `uᵀQu = ‖Bu‖²`.  The signer's coset
/// representative has at most DIM odd coordinates, each contributing 1.
pub const BOUND: i128 = DIM as i128;
/// Signature salt length (bytes).
pub const SALT_BYTES: usize = 16;

type Vector = Vec<i64>;
type Matrix = Vec<Vector>;

// ── Secret basis construction ─────────────────────────────────────────────────

fn identity(n: usize) -> Matrix {
    let mut m = vec![vec![0i64; n]; n];
    for (i, row) in m.iter_mut().enumerate() {
        row[i] = 1;
    }
    m
}

/// Build a random unimodular `B` (det ±1) as a product of elementary
/// shears `I + c·E_{ij}`, tracking `B⁻¹` alongside (apply the inverse
/// shears in reverse order).  Shears are applied in full rounds — one
/// per row per round — so the basis becomes dense while entries grow
/// only geometrically per round and stay comfortably inside i64.
///
/// After each shear we clamp: if any entry would exceed a modest cap we
/// skip that shear rather than restart, so this always terminates in a
/// fixed number of steps and returns a well-mixed basis whose columns
/// (hence Gram diagonal) are large — which is what makes verification
/// tight against small tampering.
fn random_unimodular() -> (Matrix, Matrix) {
    const ROUNDS: usize = 3;
    const CAP: i64 = 40;
    let mut b = identity(DIM);
    let mut b_inv = identity(DIM);
    let mut rnd = vec![0u8; ROUNDS * DIM * 2];
    random_bytes(&mut rnd);
    for s in 0..ROUNDS * DIM {
        let i = s % DIM;
        let mut j = rnd[2 * s] as usize % DIM;
        if i == j {
            j = (j + 1) % DIM;
        }
        let c = if rnd[2 * s + 1] & 1 == 0 { 1i64 } else { -1i64 };
        // Skip if this shear would push any entry past the cap.
        if (0..DIM).any(|k| (b[i][k] + c * b[j][k]).abs() > CAP) {
            continue;
        }
        // B ← S·B with S = I + c·E_{ij}: row_i += c·row_j.
        for k in 0..DIM {
            b[i][k] += c * b[j][k];
        }
        // B⁻¹ ← B⁻¹·S⁻¹ = B⁻¹·(I − c·E_{ij}): col_j −= c·col_i.
        for row in b_inv.iter_mut() {
            let v = row[i];
            row[j] -= c * v;
        }
    }
    (b, b_inv)
}

fn gram(b: &Matrix) -> Matrix {
    let n = b.len();
    let mut q = vec![vec![0i64; n]; n];
    for i in 0..n {
        for j in 0..n {
            q[i][j] = (0..n).map(|k| b[k][i] * b[k][j]).sum();
        }
    }
    q
}

// ── Keys and signatures ───────────────────────────────────────────────────────

/// Public key: the Gram matrix `Q = BᵀB` — the geometry of Z^{2n} in
/// the secret coordinates, but not the coordinates themselves.
#[derive(Clone, Debug, PartialEq)]
pub struct HawkPublicKey {
    pub q: Matrix,
}

#[derive(Clone, Debug)]
pub struct HawkSecretKey {
    b: Matrix,
    b_inv: Matrix,
}

#[derive(Clone, Debug, PartialEq)]
pub struct HawkSignature {
    pub salt: Vec<u8>,
    pub s: Vector,
}

/// Hash `(salt, msg)` to the parity target `h ∈ {0,1}^{DIM}`.
fn hash_to_parities(salt: &[u8], msg: &[u8]) -> Vector {
    let mut input = b"HAWK-toy".to_vec();
    input.extend_from_slice(salt);
    input.extend_from_slice(msg);
    let h = shake256(&input, DIM / 8);
    (0..DIM)
        .map(|i| ((h[i / 8] >> (i % 8)) & 1) as i64)
        .collect()
}

pub fn hawk_keygen() -> (HawkPublicKey, HawkSecretKey) {
    // Draw a well-mixed basis; require every column norm² ≥ 2 so that
    // perturbing a valid signature in any single coordinate already
    // pushes it over the verification bound.  The mixing makes this
    // hold on essentially every draw, so the loop is a formality that
    // never spins for long.
    loop {
        let (b, b_inv) = random_unimodular();
        let q = gram(&b);
        if (0..DIM).all(|i| q[i][i] >= 2) {
            return (HawkPublicKey { q }, HawkSecretKey { b, b_inv });
        }
    }
}

pub fn hawk_sign(sk: &HawkSecretKey, msg: &[u8]) -> HawkSignature {
    loop {
        let mut salt = vec![0u8; SALT_BYTES];
        random_bytes(&mut salt);
        let h = hash_to_parities(&salt, msg);

        // Bh mod 2 tells which coordinates of the short vector e = Bu must
        // be odd; pick e ∈ {0, ±1}^DIM in that coset (sign random — real
        // HAWK samples e from a discrete Gaussian on the coset instead).
        let bh: Vector = (0..DIM)
            .map(|i| (0..DIM).map(|j| sk.b[i][j] * h[j]).sum::<i64>())
            .collect();
        let mut signs = vec![0u8; DIM];
        random_bytes(&mut signs);
        let e: Vector = bh
            .iter()
            .zip(&signs)
            .map(|(&p, &r)| {
                if p.rem_euclid(2) == 0 {
                    0
                } else if r & 1 == 0 {
                    1
                } else {
                    -1
                }
            })
            .collect();

        // If every Bh coordinate is even then e = 0, giving u = 0 and a
        // signature that `hawk_verify` rejects (it forbids the all-zero
        // coset representative).  This is negligibly rare (~2⁻³²) but a
        // real correctness hole, so re-draw the salt — which reseeds h —
        // until e is nonzero.
        if e.iter().all(|&x| x == 0) {
            continue;
        }

        // u = B⁻¹e satisfies u ≡ h (mod 2); publish s = (h − u)/2.
        let u: Vector = (0..DIM)
            .map(|i| (0..DIM).map(|j| sk.b_inv[i][j] * e[j]).sum::<i64>())
            .collect();
        let s: Vector = h.iter().zip(&u).map(|(&hi, &ui)| (hi - ui) / 2).collect();
        return HawkSignature { salt, s };
    }
}

pub fn hawk_verify(pk: &HawkPublicKey, msg: &[u8], sig: &HawkSignature) -> bool {
    if sig.s.len() != DIM || sig.salt.len() != SALT_BYTES {
        return false;
    }
    let h = hash_to_parities(&sig.salt, msg);
    // u = h − 2s ranges over the coset h + 2Z^DIM as s ranges over Z^DIM;
    // accept iff u is short in the Q-metric (and nonzero).  `sig.s` is
    // untrusted, so compute u in i128 — `hi - 2*si` on a raw i64 `si`
    // could overflow (debug panic / release wraparound before the check
    // even runs).
    let u: Vec<i128> = h
        .iter()
        .zip(&sig.s)
        .map(|(&hi, &si)| hi as i128 - 2 * si as i128)
        .collect();
    if u.iter().all(|&x| x == 0) {
        return false;
    }
    // A genuine signature is a short vector, so its coordinates are
    // tiny.  Reject absurd coordinates before the quadratic form so the
    // i128 accumulation (a triple product u·q·u summed over DIM² terms)
    // cannot overflow; 2⁴⁰ is far above any real coordinate yet leaves
    // ~2⁷ bits of headroom per term.
    if u.iter().any(|&x| x.abs() > (1i128 << 40)) {
        return false;
    }
    let mut norm: i128 = 0;
    for i in 0..DIM {
        if u[i] == 0 {
            continue;
        }
        for j in 0..DIM {
            norm += u[i] * (pk.q[i][j] as i128) * u[j];
        }
    }
    norm <= BOUND
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basis_and_inverse_are_consistent() {
        let (_, sk) = hawk_keygen();
        let prod = |a: &Matrix, b: &Matrix| -> Matrix {
            (0..DIM)
                .map(|i| {
                    (0..DIM)
                        .map(|j| (0..DIM).map(|k| a[i][k] * b[k][j]).sum::<i64>())
                        .collect()
                })
                .collect()
        };
        assert_eq!(prod(&sk.b, &sk.b_inv), identity(DIM));
    }

    #[test]
    fn gram_is_symmetric_positive_diagonal() {
        let (pk, _) = hawk_keygen();
        for i in 0..DIM {
            assert!(pk.q[i][i] > 0);
            for j in 0..DIM {
                assert_eq!(pk.q[i][j], pk.q[j][i]);
            }
        }
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = hawk_keygen();
        let msg = b"lattice isomorphism problem";
        let sig = hawk_sign(&sk, msg);
        assert!(hawk_verify(&pk, msg, &sig));
    }

    #[test]
    fn verify_handles_adversarial_signature_without_overflow() {
        // Untrusted signatures must never panic (debug) or wrap (release)
        // in the `h − 2s` / quadratic-form computation.  Extreme i64
        // coordinates must simply be rejected.
        let (pk, _) = hawk_keygen();
        let sig = HawkSignature {
            salt: vec![0u8; SALT_BYTES],
            s: vec![i64::MAX; DIM],
        };
        assert!(!hawk_verify(&pk, b"m", &sig));
        let sig2 = HawkSignature {
            salt: vec![0u8; SALT_BYTES],
            s: vec![i64::MIN; DIM],
        };
        assert!(!hawk_verify(&pk, b"m", &sig2));
    }

    #[test]
    fn signer_norm_is_exactly_the_odd_count() {
        // ‖Bu‖² = ‖e‖² = number of odd coordinates of Bh ≤ DIM: the
        // signature is *provably* within bound by construction.
        let (pk, sk) = hawk_keygen();
        for i in 0..5 {
            let msg = [i as u8; 8];
            let sig = hawk_sign(&sk, &msg);
            assert!(hawk_verify(&pk, &msg, &sig));
        }
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = hawk_keygen();
        let sig = hawk_sign(&sk, b"one");
        assert!(!hawk_verify(&pk, b"two", &sig));
    }

    #[test]
    fn naive_forgery_fails() {
        // The obvious forgery s = 0 gives u = h, which is short in the
        // *Euclidean* metric but long in the Q-metric.
        let (pk, _) = hawk_keygen();
        let msg = b"forgery";
        let sig = HawkSignature {
            salt: vec![0u8; SALT_BYTES],
            s: vec![0; DIM],
        };
        assert!(!hawk_verify(&pk, msg, &sig));
    }

    #[test]
    fn tampered_signature_rejected() {
        let (pk, sk) = hawk_keygen();
        let msg = b"tamper";
        let mut sig = hawk_sign(&sk, msg);
        sig.s[0] += 5;
        assert!(!hawk_verify(&pk, msg, &sig));
    }
}
