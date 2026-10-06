//! Chosen-ciphertext key recovery against ML-KEM from decapsulation leakage.
//!
//! ML-KEM is IND-CCA2 secure, and nothing here contradicts that. What this
//! module attacks is the gap the Fujisaki–Okamoto transform leaves open in
//! *implementations*: decapsulation decrypts the attacker's ciphertext with the
//! long-term secret before it decides to reject it. The decision is made in
//! constant time and the output is an implicit-rejection value that reveals
//! nothing — but the decryption happened, and on real hardware the plaintext
//! that came out of it leaks.
//!
//! That leak is the single most practically important attack surface these
//! schemes have, and it is the reason this module exists alongside the lattice
//! estimators in [`crate::cryptanalysis::mlwe`]. Breaking ML-KEM-768 by lattice
//! reduction costs `2^180`-ish. Breaking it with a few thousand decapsulation
//! traces costs an afternoon.
//!
//! # The two oracles
//!
//! Both are standard in the side-channel literature and differ only in how much
//! one query yields:
//!
//! * [`FullDecryptionOracle`] — the whole 32-byte `m'`. Models leakage on the
//!   message-decoding step (`Compress_1` over 256 coefficients, one bit each,
//!   which on many implementations is a visibly data-dependent loop).
//!   Recovers the entire secret in a couple of dozen queries.
//! * [`PlaintextCheckingOracle`] — one bit, "did `m'` equal this `m`?". Models
//!   leakage on the FO re-encryption comparison, or on the hash of `m'`. This
//!   is the weaker and more commonly available oracle, and it needs a few
//!   thousand queries — which is the order the published attacks report.
//!
//! # The technique
//!
//! `K-PKE.Decrypt` computes `m = Compress₁(Decompress(v) - Σᵢ sᵢ·Decompress(uᵢ))`.
//! Nothing constrains the attacker to send a *well-formed* ciphertext: `u` and
//! `v` are just packed integers. So set
//!
//! ```text
//! u₀ = U·X⁰,   uᵢ = 0 for i > 0,   v = V·Xʲ
//! ```
//!
//! and the decryption collapses to `w[t] = (t == j ? V : 0) - U·s₀[t]`. Choose
//! `U` small enough that `U·η < q/4` and every `t ≠ j` decodes to 0 regardless
//! of the secret; then bit `j` of `m'` is `Compress₁(V - U·s₀[j])`, a threshold
//! test on one secret coefficient. A handful of `(U, V)` pairs separates all
//! `2η+1` possible values, and the oracle reads the answer off.
//!
//! For the full-decryption oracle the same idea runs 256 times wider: put `V`
//! at *every* coefficient of `v` and one query tests all 256 coefficients of a
//! component at once.
//!
//! # References
//!
//! * Ravi, Roy, Chattopadhyay, Bhasin, *Generic side-channel attacks on
//!   CCA-secure lattice-based PKE and KEMs*, TCHES 2020 — the plaintext-checking
//!   oracle formulation and the chosen-ciphertext structure used here.
//! * Ueno, Xagawa, Tanaka, Ito, Takahashi, Homma, *Curse of re-encryption*,
//!   TCHES 2022 — the same attack driven by leakage on the FO comparison.

use crate::hash::sha3::{sha3_256, sha3_512};
use crate::pqc::ml_kem::{
    kpke_decrypt_for_analysis, ml_kem_encaps_internal, ml_kem_keygen_internal,
    secret_coefficients_for_analysis, MlKemDecapsKey, MlKemParams, ML_KEM_1024, ML_KEM_512,
    ML_KEM_768,
};

/// ML-KEM's modulus.
pub const Q: i32 = 3329;
/// Polynomial degree.
pub const N: usize = 256;

/// `Compress_d`, as FIPS 203 §4.2.1 defines it.
pub fn compress(x: i32, d: usize) -> u16 {
    let x = x.rem_euclid(Q) as i64;
    ((((x << d) + (Q as i64) / 2) / Q as i64) & ((1i64 << d) - 1)) as u16
}

/// `Decompress_d`.
pub fn decompress(y: u16, d: usize) -> i32 {
    (((y as i64) * Q as i64 + (1i64 << (d - 1))) >> d) as i32
}

/// Pack 256 `d`-bit values little-endian into `32·d` bytes (`ByteEncode_d`).
pub fn pack(values: &[u16; N], d: usize) -> Vec<u8> {
    let mut out = vec![0u8; 32 * d];
    for (i, &c) in values.iter().enumerate() {
        for b in 0..d {
            if (c >> b) & 1 == 1 {
                let idx = i * d + b;
                out[idx / 8] |= 1 << (idx % 8);
            }
        }
    }
    out
}

/// Assemble a ciphertext directly from compressed coefficients.
///
/// `u_component` selects which module component carries the nonzero `u`; every
/// other component is the zero polynomial. `u_value` is the compressed
/// coefficient placed at `u`'s constant term. `v` is given in full so a caller
/// can put `V` at one position or at all of them.
pub fn craft_ciphertext(
    p: &MlKemParams,
    u_component: usize,
    u_value: u16,
    v: &[u16; N],
) -> Vec<u8> {
    let mut c = Vec::with_capacity(p.ct_len());
    for i in 0..p.k {
        let mut poly = [0u16; N];
        if i == u_component {
            poly[0] = u_value;
        }
        c.extend_from_slice(&pack(&poly, p.du));
    }
    c.extend_from_slice(&pack(v, p.dv));
    c
}

// ── Oracles ──────────────────────────────────────────────────────────────────

/// A decapsulation that leaks the decrypted plaintext in full.
pub struct FullDecryptionOracle<'a> {
    params: &'a MlKemParams,
    dk_pke: Vec<u8>,
    queries: u64,
}

/// A decapsulation that leaks only whether the decrypted plaintext matched a
/// guess: one bit per query.
pub struct PlaintextCheckingOracle<'a> {
    inner: FullDecryptionOracle<'a>,
}

impl<'a> FullDecryptionOracle<'a> {
    /// Wrap a decapsulation key. Only the K-PKE part is used — the attack never
    /// touches `z`, `H(ek)` or the implicit-rejection path, because the leak it
    /// models happens before those.
    pub fn new(params: &'a MlKemParams, dk: &MlKemDecapsKey) -> Self {
        FullDecryptionOracle {
            params,
            dk_pke: dk.0[..384 * params.k].to_vec(),
            queries: 0,
        }
    }

    /// One query: the plaintext `K-PKE.Decrypt` produced.
    pub fn decrypt(&mut self, c: &[u8]) -> [u8; 32] {
        self.queries += 1;
        kpke_decrypt_for_analysis(self.params, &self.dk_pke, c)
    }

    pub fn queries(&self) -> u64 {
        self.queries
    }
}

impl<'a> PlaintextCheckingOracle<'a> {
    pub fn new(params: &'a MlKemParams, dk: &MlKemDecapsKey) -> Self {
        PlaintextCheckingOracle {
            inner: FullDecryptionOracle::new(params, dk),
        }
    }

    /// One query: did the decryption of `c` equal `m`?
    pub fn check(&mut self, c: &[u8], m: &[u8; 32]) -> bool {
        &self.inner.decrypt(c) == m
    }

    pub fn queries(&self) -> u64 {
        self.inner.queries()
    }
}

// ── Query planning ───────────────────────────────────────────────────────────

/// A chosen `(U_compressed, V_compressed)` pair, with the bit each secret value
/// would produce.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Query {
    pub u_value: u16,
    pub v_value: u16,
    /// `bits[i]` is the decoded bit when the secret coefficient equals
    /// `i as i32 - eta`.
    pub bits: Vec<u8>,
}

/// Build a set of queries whose combined bit patterns separate every possible
/// secret coefficient value.
///
/// `silent` demands that `U·η < q/4`, so every coefficient the query is *not*
/// aimed at decodes to zero whatever the secret is. The plaintext-checking
/// oracle needs that (it compares the whole 32-byte plaintext); the
/// full-decryption oracle does not, and dropping the constraint gives it a
/// wider choice of `U`.
///
/// Returns `None` if no set of queries separates the values, which would mean
/// the parameter set's compression grids are too coarse — it does not happen
/// for the three standardised sets, and the test in this file says so.
pub fn plan_queries(p: &MlKemParams, eta: usize, silent: bool) -> Option<Vec<Query>> {
    let values: Vec<i32> = (-(eta as i32)..=(eta as i32)).collect();
    let mut candidates: Vec<Query> = Vec::new();
    for ku in 1u16..(1 << p.du) {
        let u = decompress(ku, p.du);
        if silent && u * eta as i32 >= Q / 4 {
            continue;
        }
        if u == 0 {
            continue;
        }
        for kv in 0u16..(1 << p.dv) {
            let v = decompress(kv, p.dv);
            let bits: Vec<u8> = values
                .iter()
                .map(|&s| compress(v - u * s, 1) as u8)
                .collect();
            // A query that answers the same for every value tells us nothing.
            if bits.iter().all(|&b| b == bits[0]) {
                continue;
            }
            candidates.push(Query {
                u_value: ku,
                v_value: kv,
                bits,
            });
        }
    }

    // Greedy set cover over "which pairs of values does this query separate".
    let mut chosen: Vec<Query> = Vec::new();
    let mut signatures: Vec<Vec<u8>> = vec![Vec::new(); values.len()];
    for _ in 0..values.len() {
        let distinct = |sigs: &[Vec<u8>]| {
            let mut s = sigs.to_vec();
            s.sort();
            s.dedup();
            s.len()
        };
        if distinct(&signatures) == values.len() {
            break;
        }
        let mut best: Option<(usize, &Query)> = None;
        for c in &candidates {
            let mut trial = signatures.clone();
            for (t, b) in trial.iter_mut().zip(&c.bits) {
                t.push(*b);
            }
            let d = distinct(&trial);
            if best.as_ref().map(|(bd, _)| d > *bd).unwrap_or(true) {
                best = Some((d, c));
            }
        }
        let (d, q) = best?;
        if d == distinct(&signatures) {
            // No query improves separation: the grids cannot resolve the values.
            return None;
        }
        for (t, b) in signatures.iter_mut().zip(&q.bits) {
            t.push(*b);
        }
        chosen.push(q.clone());
    }

    let mut sorted = signatures.clone();
    sorted.sort();
    sorted.dedup();
    if sorted.len() == values.len() {
        Some(chosen)
    } else {
        None
    }
}

/// Map a signature (one bit per query) back to the secret value that produces
/// it.
fn decode_signature(queries: &[Query], eta: usize, sig: &[u8]) -> Option<i16> {
    let values: Vec<i32> = (-(eta as i32)..=(eta as i32)).collect();
    'outer: for (idx, &v) in values.iter().enumerate() {
        for (q, &b) in queries.iter().zip(sig) {
            if q.bits[idx] != b {
                continue 'outer;
            }
        }
        return Some(v as i16);
    }
    None
}

// ── The attacks ──────────────────────────────────────────────────────────────

/// What an attack run did.
#[derive(Clone, Debug, PartialEq)]
pub struct AttackReport {
    pub parameter_set: String,
    pub oracle: &'static str,
    /// Oracle queries consumed.
    pub queries: u64,
    /// Coefficients recovered, i.e. `256·k`.
    pub coefficients: usize,
    /// How many matched the true secret.
    pub correct: usize,
    /// Whether the recovered key decapsulates an honest ciphertext correctly —
    /// the end-to-end check, independent of the coefficient comparison.
    pub decapsulates: bool,
}

impl AttackReport {
    pub fn succeeded(&self) -> bool {
        self.correct == self.coefficients && self.decapsulates
    }
}

/// Recover the whole K-PKE secret from a full-decryption oracle.
///
/// One query per `(component, plan step)`: with `k` components and a plan of
/// three or four steps, that is a dozen or two queries for the entire key.
pub fn recover_with_full_decryption(
    p: &MlKemParams,
    oracle: &mut FullDecryptionOracle,
) -> Option<Vec<Vec<i16>>> {
    let plan = plan_queries(p, p.eta1, false)?;
    let mut secret = Vec::with_capacity(p.k);
    for comp in 0..p.k {
        // sig[j] accumulates one bit per plan step for coefficient j.
        let mut sigs: Vec<Vec<u8>> = vec![Vec::new(); N];
        for q in &plan {
            let v = [q.v_value; N];
            let c = craft_ciphertext(p, comp, q.u_value, &v);
            let m = oracle.decrypt(&c);
            for (j, sig) in sigs.iter_mut().enumerate() {
                sig.push((m[j / 8] >> (j % 8)) & 1);
            }
        }
        let mut coeffs = Vec::with_capacity(N);
        for sig in &sigs {
            coeffs.push(decode_signature(&plan, p.eta1, sig)?);
        }
        secret.push(coeffs);
    }
    Some(secret)
}

/// Recover the whole K-PKE secret from a one-bit plaintext-checking oracle.
///
/// One query per `(component, coefficient, plan step)`. The `silent` planning
/// constraint is what makes this work: every coefficient the query is not
/// aimed at must decode to zero, or the equality test would answer "no" for
/// reasons unrelated to the bit being probed.
pub fn recover_with_pc_oracle(
    p: &MlKemParams,
    oracle: &mut PlaintextCheckingOracle,
) -> Option<Vec<Vec<i16>>> {
    let plan = plan_queries(p, p.eta1, true)?;
    let mut secret = Vec::with_capacity(p.k);
    for comp in 0..p.k {
        let mut coeffs = Vec::with_capacity(N);
        for j in 0..N {
            let mut sig = Vec::with_capacity(plan.len());
            for q in &plan {
                let mut v = [0u16; N];
                v[j] = q.v_value;
                let c = craft_ciphertext(p, comp, q.u_value, &v);
                // The expected plaintext when bit j is 1 and all others are 0.
                let mut m = [0u8; 32];
                m[j / 8] = 1 << (j % 8);
                sig.push(u8::from(oracle.check(&c, &m)));
            }
            coeffs.push(decode_signature(&plan, p.eta1, &sig)?);
        }
        secret.push(coeffs);
    }
    Some(secret)
}

// ── Using the recovered key ──────────────────────────────────────────────────

/// Negacyclic product in `R_q = Z_q[X]/(X^256+1)`, schoolbook.
///
/// The attack module does its own arithmetic rather than borrowing the
/// scheme's, so "the recovered key decapsulates" is a claim checked by
/// independent code.
pub fn poly_mul(a: &[i32; N], b: &[i32; N]) -> [i32; N] {
    let mut out = [0i64; N];
    for (i, &ai) in a.iter().enumerate() {
        if ai == 0 {
            continue;
        }
        for (j, &bj) in b.iter().enumerate() {
            let k = i + j;
            if k < N {
                out[k] += ai as i64 * bj as i64;
            } else {
                out[k - N] -= ai as i64 * bj as i64;
            }
        }
    }
    let mut r = [0i32; N];
    for i in 0..N {
        r[i] = out[i].rem_euclid(Q as i64) as i32;
    }
    r
}

/// Unpack `32·d` bytes into 256 `d`-bit values.
pub fn unpack(bytes: &[u8], d: usize) -> [u16; N] {
    let mut out = [0u16; N];
    for (i, o) in out.iter_mut().enumerate() {
        let mut c = 0u16;
        for b in 0..d {
            let idx = i * d + b;
            c |= (((bytes[idx / 8] >> (idx % 8)) & 1) as u16) << b;
        }
        *o = c;
    }
    out
}

/// Decrypt a K-PKE ciphertext with a recovered secret, in this module's own
/// arithmetic.
pub fn decrypt_with_recovered(p: &MlKemParams, s: &[Vec<i16>], c: &[u8]) -> [u8; 32] {
    let u_bytes = 32 * p.du;
    let mut acc = [0i32; N];
    for i in 0..p.k {
        let packed = unpack(&c[u_bytes * i..u_bytes * (i + 1)], p.du);
        let mut u = [0i32; N];
        for j in 0..N {
            u[j] = decompress(packed[j], p.du);
        }
        let mut si = [0i32; N];
        for j in 0..N {
            si[j] = s[i][j] as i32;
        }
        let prod = poly_mul(&si, &u);
        for j in 0..N {
            acc[j] = (acc[j] + prod[j]) % Q;
        }
    }
    let packed_v = unpack(&c[u_bytes * p.k..], p.dv);
    let mut m = [0u8; 32];
    for j in 0..N {
        let w = decompress(packed_v[j], p.dv) - acc[j];
        if compress(w, 1) == 1 {
            m[j / 8] |= 1 << (j % 8);
        }
    }
    m
}

/// The shared secret an attacker derives after recovering the key: decrypt to
/// `m'`, then re-run the FO's key derivation. Equal to the honest `K` exactly
/// when the recovery worked.
pub fn shared_secret_from_recovered(
    p: &MlKemParams,
    s: &[Vec<i16>],
    ek: &[u8],
    c: &[u8],
) -> [u8; 32] {
    let m = decrypt_with_recovered(p, s, c);
    let mut input = m.to_vec();
    input.extend_from_slice(&sha3_256(ek));
    let g = sha3_512(&input);
    let mut k = [0u8; 32];
    k.copy_from_slice(&g[..32]);
    k
}

/// Run one attack end to end against a freshly generated key pair.
///
/// `full` selects the full-decryption oracle; otherwise the one-bit
/// plaintext-checking oracle. `seed` makes the run reproducible.
pub fn run_attack(p: &MlKemParams, full: bool, seed: u8) -> Option<AttackReport> {
    let d = [seed; 32];
    let z = [seed ^ 0xff; 32];
    let (ek, dk) = ml_kem_keygen_internal(p, &d, &z);
    let truth = secret_coefficients_for_analysis(p, &dk.0[..384 * p.k]);

    let (recovered, queries, oracle_name) = if full {
        let mut o = FullDecryptionOracle::new(p, &dk);
        let r = recover_with_full_decryption(p, &mut o)?;
        (r, o.queries(), "full-decryption")
    } else {
        let mut o = PlaintextCheckingOracle::new(p, &dk);
        let r = recover_with_pc_oracle(p, &mut o)?;
        (r, o.queries(), "plaintext-checking")
    };

    let coefficients = p.k * N;
    let correct = truth
        .iter()
        .zip(&recovered)
        .map(|(t, r)| t.iter().zip(r).filter(|(a, b)| a == b).count())
        .sum();

    // End-to-end: encapsulate honestly, then derive the shared secret from the
    // recovered key alone.
    let m = [seed.wrapping_mul(7).wrapping_add(1); 32];
    let (ct, k_true) = ml_kem_encaps_internal(p, &ek, &m)?;
    let k_attacker = shared_secret_from_recovered(p, &recovered, &ek.0, &ct);

    Some(AttackReport {
        parameter_set: p.name.to_string(),
        oracle: oracle_name,
        queries,
        coefficients,
        correct,
        decapsulates: k_attacker == k_true,
    })
}

/// The three standardised parameter sets, for the CLI.
pub fn parameter_set(name: &str) -> Option<&'static MlKemParams> {
    let key: String = name
        .chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .map(|c| c.to_ascii_lowercase())
        .collect();
    match key.as_str() {
        "mlkem512" | "512" => Some(&ML_KEM_512),
        "mlkem768" | "768" => Some(&ML_KEM_768),
        "mlkem1024" | "1024" => Some(&ML_KEM_1024),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compress_and_decompress_round_trip_within_the_grid() {
        for d in [1usize, 4, 5, 10, 11] {
            for y in 0..(1u16 << d) {
                let x = decompress(y, d);
                assert!((0..Q).contains(&x));
                assert_eq!(compress(x, d), y, "d = {d}, y = {y}");
            }
        }
    }

    #[test]
    fn compress_1_is_the_half_interval_test() {
        // Compress₁(x) = 1 exactly on the middle half of Z_q.
        assert_eq!(compress(0, 1), 0);
        assert_eq!(compress(832, 1), 0);
        assert_eq!(compress(833, 1), 1);
        assert_eq!(compress(2496, 1), 1);
        assert_eq!(compress(2497, 1), 0);
        assert_eq!(compress(Q - 1, 1), 0);
        // Negative inputs are reduced first.
        assert_eq!(compress(-1, 1), 0);
        assert_eq!(compress(-(Q / 2), 1), 1);
    }

    #[test]
    fn pack_and_unpack_are_inverse() {
        for d in [1usize, 4, 5, 10, 11, 12] {
            let mut v = [0u16; N];
            for (i, x) in v.iter_mut().enumerate() {
                *x = ((i as u32).wrapping_mul(2_654_435_761) % (1u32 << d)) as u16;
            }
            let bytes = pack(&v, d);
            assert_eq!(bytes.len(), 32 * d);
            assert_eq!(unpack(&bytes, d), v);
        }
    }

    #[test]
    fn crafted_ciphertexts_have_the_right_length() {
        for p in [&ML_KEM_512, &ML_KEM_768, &ML_KEM_1024] {
            let c = craft_ciphertext(p, 0, 1, &[0u16; N]);
            assert_eq!(c.len(), p.ct_len());
        }
    }

    #[test]
    fn a_separating_query_plan_exists_for_every_parameter_set() {
        for p in [&ML_KEM_512, &ML_KEM_768, &ML_KEM_1024] {
            for silent in [false, true] {
                let plan = plan_queries(p, p.eta1, silent)
                    .unwrap_or_else(|| panic!("{} silent={silent}: no plan", p.name));
                // A plan cannot be shorter than log2 of the number of values.
                let values = 2 * p.eta1 + 1;
                assert!(plan.len() >= (values as f64).log2().ceil() as usize);
                // …and should not need more than one query per value.
                assert!(plan.len() <= values, "{}: plan of {}", p.name, plan.len());
                // Signatures must be distinct, which is what the plan is for.
                let sigs: Vec<Vec<u8>> = (0..values)
                    .map(|i| plan.iter().map(|q| q.bits[i]).collect())
                    .collect();
                let mut s = sigs.clone();
                s.sort();
                s.dedup();
                assert_eq!(s.len(), values, "{} silent={silent}", p.name);
            }
        }
    }

    #[test]
    fn the_silent_constraint_really_is_silent() {
        // Every non-targeted coefficient must decode to 0 for any secret value
        // in range — that is the whole premise of the one-bit attack.
        for p in [&ML_KEM_512, &ML_KEM_768, &ML_KEM_1024] {
            let plan = plan_queries(p, p.eta1, true).unwrap();
            for q in &plan {
                let u = decompress(q.u_value, p.du);
                for s in -(p.eta1 as i32)..=(p.eta1 as i32) {
                    assert_eq!(compress(-u * s, 1), 0, "{}: U = {u}, s = {s}", p.name);
                }
            }
        }
    }

    #[test]
    fn decode_signature_inverts_the_plan() {
        for p in [&ML_KEM_512, &ML_KEM_768] {
            let plan = plan_queries(p, p.eta1, true).unwrap();
            for (i, s) in (-(p.eta1 as i32)..=(p.eta1 as i32)).enumerate() {
                let sig: Vec<u8> = plan.iter().map(|q| q.bits[i]).collect();
                assert_eq!(decode_signature(&plan, p.eta1, &sig), Some(s as i16));
            }
        }
    }

    #[test]
    fn poly_mul_matches_the_negacyclic_definition() {
        // X^255 · X = X^256 = -1.
        let mut a = [0i32; N];
        a[255] = 1;
        let mut b = [0i32; N];
        b[1] = 1;
        let c = poly_mul(&a, &b);
        assert_eq!(c[0], Q - 1);
        assert!(c[1..].iter().all(|&x| x == 0));
        // Multiplication by 1 is the identity.
        let mut one = [0i32; N];
        one[0] = 1;
        let mut r = [0i32; N];
        for (i, x) in r.iter_mut().enumerate() {
            *x = (i as i32 * 13) % Q;
        }
        assert_eq!(poly_mul(&r, &one), r);
    }

    #[test]
    fn full_decryption_oracle_recovers_ml_kem_512_exactly() {
        let r = run_attack(&ML_KEM_512, true, 1).expect("attack ran");
        assert_eq!(r.correct, r.coefficients, "{r:?}");
        assert!(r.decapsulates, "{r:?}");
        assert!(r.succeeded());
        // A couple of dozen queries for the whole key: k components times a
        // plan of a few steps.
        assert!(r.queries < 40, "{} queries", r.queries);
    }

    #[test]
    fn full_decryption_oracle_recovers_every_parameter_set() {
        for p in [&ML_KEM_512, &ML_KEM_768, &ML_KEM_1024] {
            let r = run_attack(p, true, 7).unwrap_or_else(|| panic!("{}", p.name));
            assert!(r.succeeded(), "{}: {r:?}", p.name);
            assert_eq!(r.coefficients, p.k * N);
        }
    }

    #[test]
    fn plaintext_checking_oracle_recovers_ml_kem_512() {
        let r = run_attack(&ML_KEM_512, false, 3).expect("attack ran");
        assert!(r.succeeded(), "{r:?}");
        // One bit per query, three bits per coefficient, 512 coefficients.
        assert!(r.queries >= r.coefficients as u64, "{} queries", r.queries);
        assert!(
            r.queries < 8 * r.coefficients as u64,
            "{} queries",
            r.queries
        );
    }

    #[test]
    fn plaintext_checking_oracle_recovers_ml_kem_768() {
        let r = run_attack(&ML_KEM_768, false, 5).expect("attack ran");
        assert!(r.succeeded(), "{r:?}");
    }

    #[test]
    fn the_one_bit_oracle_costs_far_more_queries_than_the_full_one() {
        // The whole difference between the two leakage models, in one number.
        let full = run_attack(&ML_KEM_512, true, 9).unwrap();
        let pc = run_attack(&ML_KEM_512, false, 9).unwrap();
        assert!(full.succeeded() && pc.succeeded());
        assert!(
            pc.queries > 40 * full.queries,
            "{} vs {}",
            pc.queries,
            full.queries
        );
    }

    #[test]
    fn recovery_is_stable_across_keys() {
        for seed in [11u8, 23, 47] {
            let r = run_attack(&ML_KEM_512, true, seed).unwrap();
            assert!(r.succeeded(), "seed {seed}: {r:?}");
        }
    }

    #[test]
    fn the_recovered_key_decapsulates_ciphertexts_it_never_saw() {
        // Independent of the coefficient comparison: recover, then decapsulate
        // several honest ciphertexts and match the real shared secret.
        let p = &ML_KEM_512;
        let (ek, dk) = ml_kem_keygen_internal(p, &[42u8; 32], &[7u8; 32]);
        let mut o = FullDecryptionOracle::new(p, &dk);
        let s = recover_with_full_decryption(p, &mut o).unwrap();
        for t in 0u8..8 {
            let m = [t.wrapping_mul(31).wrapping_add(5); 32];
            let (ct, k_true) = ml_kem_encaps_internal(p, &ek, &m).unwrap();
            assert_eq!(
                shared_secret_from_recovered(p, &s, &ek.0, &ct),
                k_true,
                "t = {t}"
            );
        }
    }

    #[test]
    fn recovered_coefficients_are_in_the_cbd_range() {
        let p = &ML_KEM_768;
        let (_, dk) = ml_kem_keygen_internal(p, &[1u8; 32], &[2u8; 32]);
        let mut o = FullDecryptionOracle::new(p, &dk);
        let s = recover_with_full_decryption(p, &mut o).unwrap();
        assert_eq!(s.len(), p.k);
        for comp in &s {
            assert_eq!(comp.len(), N);
            for &c in comp {
                assert!(
                    c.unsigned_abs() as usize <= p.eta1,
                    "coefficient {c} out of range"
                );
            }
        }
    }

    #[test]
    fn parameter_set_lookup_accepts_the_cli_spellings() {
        assert_eq!(parameter_set("ml-kem-768").unwrap().k, 3);
        assert_eq!(parameter_set("MLKEM1024").unwrap().k, 4);
        assert_eq!(parameter_set("512").unwrap().k, 2);
        assert!(parameter_set("ml-kem-640").is_none());
    }
}
