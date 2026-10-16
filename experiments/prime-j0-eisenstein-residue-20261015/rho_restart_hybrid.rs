//! Matched public-scalar rho restart kernel on secp256k1.
//! `openssl` computes aG+bQ through one EC_POINT_mul call. `hybrid` uses the
//! norm-4033 fixed-base table for aG, then OpenSSL for bQ and final addition.
//! Both arms include affine output conversion in their online interval.

use std::ffi::{c_int, c_void};
use std::ptr;
use std::time::Instant;

use num_bigint::BigInt;
use serde_json::Value;

use super::{scalar_words_256, unit_orbit_windows};

#[link(name = "crypto")]
unsafe extern "C" {
    fn EC_GROUP_new_by_curve_name(nid: c_int) -> *mut c_void;
    fn EC_GROUP_free(group: *mut c_void);
    fn EC_POINT_new(group: *const c_void) -> *mut c_void;
    fn EC_POINT_free(point: *mut c_void);
    fn EC_POINT_set_affine_coordinates(group: *const c_void, point: *mut c_void,
                                       x: *const c_void, y: *const c_void,
                                       ctx: *mut c_void) -> c_int;
    fn EC_POINT_get_affine_coordinates(group: *const c_void, point: *const c_void,
                                       x: *mut c_void, y: *mut c_void,
                                       ctx: *mut c_void) -> c_int;
    fn EC_POINT_mul(group: *const c_void, result: *mut c_void,
                    generator_scalar: *const c_void, point: *const c_void,
                    point_scalar: *const c_void, ctx: *mut c_void) -> c_int;
    fn EC_POINT_add(group: *const c_void, result: *mut c_void,
                    left: *const c_void, right: *const c_void,
                    ctx: *mut c_void) -> c_int;
    fn BN_CTX_new() -> *mut c_void;
    fn BN_CTX_free(ctx: *mut c_void);
    fn BN_new() -> *mut c_void;
    fn BN_free(number: *mut c_void);
    fn BN_bin2bn(bytes: *const u8, length: c_int, reuse: *mut c_void) -> *mut c_void;
    fn BN_bn2binpad(number: *const c_void, output: *mut u8, length: c_int) -> c_int;
}

struct Case {
    a_words: [u64; 4],
    a_bn: *mut c_void,
    b_bn: *mut c_void,
    expected: String,
}

struct Openssl {
    group: *mut c_void,
    ctx: *mut c_void,
    q: *mut c_void,
    result: *mut c_void,
    ag: *mut c_void,
    bq: *mut c_void,
    x: *mut c_void,
    y: *mut c_void,
}

impl Openssl {
    unsafe fn new(q_hex: &str) -> Self {
        let group = EC_GROUP_new_by_curve_name(714); // NID_secp256k1
        assert!(!group.is_null());
        let ctx = BN_CTX_new();
        let q = EC_POINT_new(group);
        let result = EC_POINT_new(group);
        let ag = EC_POINT_new(group);
        let bq = EC_POINT_new(group);
        let x = BN_new();
        let y = BN_new();
        assert!(!ctx.is_null() && !q.is_null() && !result.is_null()
                && !ag.is_null() && !bq.is_null() && !x.is_null() && !y.is_null());
        let mut state = Self { group, ctx, q, result, ag, bq, x, y };
        state.set_affine(q, q_hex);
        state
    }

    unsafe fn set_affine(&mut self, point: *mut c_void, affine: &str) {
        let (xh, yh) = affine.split_once(':').expect("x:y point");
        let xb = hex::decode(xh).expect("x hex");
        let yb = hex::decode(yh).expect("y hex");
        assert_eq!(xb.len(), 32);
        assert_eq!(yb.len(), 32);
        assert_eq!(BN_bin2bn(xb.as_ptr(), 32, self.x), self.x);
        assert_eq!(BN_bin2bn(yb.as_ptr(), 32, self.y), self.y);
        assert_eq!(EC_POINT_set_affine_coordinates(
            self.group, point, self.x, self.y, self.ctx), 1);
    }

    unsafe fn point_hex(&mut self) -> String {
        assert_eq!(EC_POINT_get_affine_coordinates(
            self.group, self.result, self.x, self.y, self.ctx), 1);
        let mut xb = [0u8; 32];
        let mut yb = [0u8; 32];
        assert_eq!(BN_bn2binpad(self.x, xb.as_mut_ptr(), 32), 32);
        assert_eq!(BN_bn2binpad(self.y, yb.as_mut_ptr(), 32), 32);
        format!("{}:{}", hex::encode(xb), hex::encode(yb))
    }

    unsafe fn baseline(&mut self, a: *const c_void, b: *const c_void) -> String {
        assert_eq!(EC_POINT_mul(self.group, self.result, a, self.q, b, self.ctx), 1);
        self.point_hex()
    }

    unsafe fn hybrid(&mut self, a_words: [u64; 4], b: *const c_void) -> String {
        let mut points = unit_orbit_windows::multiply_u256_tau_alt_split_prime_two_x_affine_batch(
            &[a_words]);
        let ag_hex = points.pop().expect("one aG point");
        self.set_affine(self.ag, &ag_hex);
        assert_eq!(EC_POINT_mul(self.group, self.bq, ptr::null(), self.q, b, self.ctx), 1);
        assert_eq!(EC_POINT_add(self.group, self.result, self.ag, self.bq, self.ctx), 1);
        self.point_hex()
    }
}

impl Drop for Openssl {
    fn drop(&mut self) {
        unsafe {
            BN_free(self.y);
            BN_free(self.x);
            EC_POINT_free(self.bq);
            EC_POINT_free(self.ag);
            EC_POINT_free(self.result);
            EC_POINT_free(self.q);
            BN_CTX_free(self.ctx);
            EC_GROUP_free(self.group);
        }
    }
}

pub(super) fn run(mode: &str, fixture_path: &str, count: usize) {
    assert!(mode == "openssl" || mode == "hybrid");
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let q_hex = fixture["q_hex"].as_str().expect("Q point");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let mut cases = Vec::with_capacity(count);
    for row in rows.iter().take(count) {
        let ah = row["a_hex"].as_str().expect("a");
        let bh = row["b_hex"].as_str().expect("b");
        let a = BigInt::parse_bytes(ah.as_bytes(), 16).expect("a hex");
        let a_words = scalar_words_256(&a).expect("a fits 256 bits");
        let ab = hex::decode(ah).expect("a bytes");
        let bb = hex::decode(bh).expect("b bytes");
        assert_eq!(ab.len(), 32);
        assert_eq!(bb.len(), 32);
        let a_bn = unsafe { BN_bin2bn(ab.as_ptr(), 32, ptr::null_mut()) };
        let b_bn = unsafe { BN_bin2bn(bb.as_ptr(), 32, ptr::null_mut()) };
        assert!(!a_bn.is_null() && !b_bn.is_null());
        cases.push(Case { a_words, a_bn, b_bn,
                          expected: row["point_hex"].as_str().expect("expected point").to_owned() });
    }
    let mut crypto = unsafe { Openssl::new(q_hex) };
    let warm_start = Instant::now();
    let warm = unsafe { crypto.baseline(cases[0].a_bn, cases[0].b_bn) };
    assert_eq!(warm, cases[0].expected);
    let openssl_warmup_ms = warm_start.elapsed().as_secs_f64() * 1000.0;
    let table_start = Instant::now();
    let retained_bytes = if mode == "hybrid" {
        unit_orbit_windows::warm_alt_split_prime_two_x_table()
    } else { 0 };
    let table_preparation_ms = table_start.elapsed().as_secs_f64() * 1000.0;
    let start = Instant::now();
    let answers = cases.iter().map(|case| unsafe {
        if mode == "hybrid" { crypto.hybrid(case.a_words, case.b_bn) }
        else { crypto.baseline(case.a_bn, case.b_bn) }
    }).collect::<Vec<_>>();
    let online_ms = start.elapsed().as_secs_f64() * 1000.0;
    for (index, (actual, case)) in answers.iter().zip(cases.iter()).enumerate() {
        assert_eq!(actual, &case.expected, "rho restart case {index}");
    }
    let point = answers.last().expect("nonempty");
    println!("verified=1 count={count} online_ms={online_ms:.6} preparation_ms={:.6} \
              openssl_warmup_ms={openssl_warmup_ms:.6} \
              table_preparation_ms={table_preparation_ms:.6} \
              retained_bytes={retained_bytes} mode={mode} point={point}",
              openssl_warmup_ms + table_preparation_ms);
    for case in cases {
        unsafe {
            BN_free(case.a_bn);
            BN_free(case.b_bn);
        }
    }
}
