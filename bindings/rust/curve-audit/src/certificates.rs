use crate::arithmetic::{primality, Primality};
use num_bigint::BigUint;
use num_traits::One;
use serde_json::Value;
use std::collections::HashSet;

const SMALL_LIMIT: u64 = 1_000_000_000_000;

pub struct VerifiedPrimes;

fn decimal(value: &Value, label: &str) -> Result<BigUint, String> {
    let text = value
        .as_str()
        .ok_or_else(|| format!("{label} must be a decimal string"))?;
    if text.is_empty() || !text.bytes().all(|b| b.is_ascii_digit()) {
        return Err(format!("{label} must be a decimal string"));
    }
    let n = BigUint::parse_bytes(text.as_bytes(), 10)
        .ok_or_else(|| format!("invalid decimal integer at {label}"))?;
    if n.bits() > 1024 {
        return Err(format!("{label} exceeds 1024 bits"));
    }
    Ok(n)
}

fn keys(value: &Value, allowed: &[&str], label: &str) -> Result<(), String> {
    let object = value
        .as_object()
        .ok_or_else(|| format!("{label} must be an object"))?;
    for key in object.keys() {
        if !allowed.contains(&key.as_str()) {
            return Err(format!("unknown {label} key: {key}"));
        }
    }
    Ok(())
}

fn verify_node(
    node: &Value,
    expected: &BigUint,
    budget: &mut usize,
    depth: usize,
) -> Result<(), String> {
    if depth > 64 || *budget == 0 {
        return Err("prime certificate exceeds the node or depth limit".into());
    }
    *budget -= 1;
    let n = decimal(&node["n"], "prime node n")?;
    if &n != expected {
        return Err("prime certificate node does not match the required integer".into());
    }
    if n <= BigUint::from(SMALL_LIMIT) {
        keys(node, &["n", "small"], "small prime node")?;
        if node["small"] != true || primality(&n) != Primality::ProvenPrime {
            return Err(format!("invalid small-prime certificate for {n}"));
        }
        return Ok(());
    }
    keys(node, &["n", "a", "factors", "sub"], "prime node")?;
    let a = decimal(&node["a"], "prime witness a")?;
    if a <= BigUint::one() || a >= n {
        return Err(format!("prime witness out of range for {n}"));
    }
    let factors = node["factors"]
        .as_array()
        .ok_or("prime factors must be an array")?;
    let sub = node["sub"]
        .as_array()
        .ok_or("prime subcertificates must be an array")?;
    if factors.is_empty() || factors.len() > 128 || sub.len() > 128 {
        return Err("prime certificate has an invalid factor count".into());
    }
    let n_minus_one = &n - BigUint::one();
    let mut product = BigUint::one();
    let mut seen = HashSet::new();
    let mut large_factors = Vec::new();
    for factor in factors {
        let pair = factor
            .as_array()
            .ok_or("factor must be [prime, exponent]")?;
        if pair.len() != 2 {
            return Err("factor must be [prime, exponent]".into());
        }
        let q = decimal(&pair[0], "factor prime")?;
        let exponent = pair[1]
            .as_u64()
            .ok_or("factor exponent must be a positive integer")?;
        if q <= BigUint::one() || q >= n || exponent == 0 || exponent > 1024 {
            return Err("factor is out of range".into());
        }
        if !seen.insert(q.clone()) {
            return Err("duplicate factor in prime certificate".into());
        }
        for _ in 0..exponent {
            product *= &q;
            if product > n_minus_one {
                return Err("prime factor product exceeds n-1".into());
            }
        }
        if q <= BigUint::from(SMALL_LIMIT) {
            if primality(&q) != Primality::ProvenPrime {
                return Err(format!("factor {q} is not prime"));
            }
        } else {
            large_factors.push(q.clone());
        }
        if a.modpow(&(&n_minus_one / &q), &n) == BigUint::one() {
            return Err(format!(
                "Lucas witness has insufficient order for factor {q}"
            ));
        }
    }
    if product != n_minus_one {
        return Err("prime factor product is not n-1".into());
    }
    if a.modpow(&n_minus_one, &n) != BigUint::one() {
        return Err("Lucas witness does not satisfy a^(n-1)=1 mod n".into());
    }
    if large_factors.len() != sub.len() {
        return Err("prime subcertificate count does not match large factors".into());
    }
    for (q, child) in large_factors.iter().zip(sub) {
        verify_node(child, q, budget, depth + 1)?;
    }
    Ok(())
}

pub fn verify(
    bytes: &[u8],
    input_sha256: &str,
    p: &BigUint,
    r: Option<&BigUint>,
) -> Result<VerifiedPrimes, String> {
    if bytes.len() > 1_000_000 {
        return Err("prime certificate exceeds 1000000 bytes".into());
    }
    let root: Value = serde_json::from_slice(bytes)
        .map_err(|e| format!("invalid prime certificate JSON: {e}"))?;
    keys(
        &root,
        &[
            "schema",
            "input_sha256",
            "field_characteristic",
            "selected_order",
        ],
        "prime certificate",
    )?;
    if root["schema"] != "ca.prime_certificates.v1" {
        return Err("prime certificate schema must be ca.prime_certificates.v1".into());
    }
    if root["input_sha256"] != input_sha256 {
        return Err("prime certificate is bound to different input bytes".into());
    }
    let r = r.ok_or("prime certificate requires input.subgroup.order")?;
    let mut budget = 256;
    verify_node(&root["field_characteristic"], p, &mut budget, 0)?;
    verify_node(&root["selected_order"], r, &mut budget, 0)?;
    Ok(VerifiedPrimes)
}
