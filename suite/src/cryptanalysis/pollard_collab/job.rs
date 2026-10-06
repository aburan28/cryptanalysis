//! Job specification: everything a peer needs to take part in a
//! collaborative rho run, and the deterministic derivations that make
//! every peer walk the *same* pseudo-random function.
//!
//! A job is a small JSON document (see [`JobSpec`]).  Its
//! [`job_id`](JobSpec::job_id) is a SHA-256 over the canonical field
//! encoding, so two peers holding byte-different files of the same
//! job agree on the id, and a peer holding a *different* job (other
//! target, other `dp_bits`, other seed) is rejected at the protocol
//! layer instead of silently polluting the DP table.
//!
//! From the id we derive, with no coordination:
//!
//! - the **branch table** of the `r`-adding walk: `B_j = u_j·P + v_j·Q`
//!   with `(u_j, v_j) = PRF(id, "branch", j)`;
//! - the **start point of walker `i`**: `R_i = a_i·P + b_i·Q` with
//!   `(a_i, b_i) = PRF(id, "walker", i)`.
//!
//! The second derivation is what divides the search space.  The
//! walker index `i ∈ [0, 2⁶⁴)` is the unit of work: unit `u` is the
//! index range `[u·unit_size, (u+1)·unit_size)`.  Two peers that never
//! talk to each other but hold disjoint index ranges never repeat a
//! trail, and any peer can re-run walker `i` to audit a claim.

use num_bigint::BigUint;
use num_traits::{One, Zero};
use serde::{Deserialize, Serialize};

use crate::ecc::curve::CurveParams;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;
use crate::hash::sha256;

/// Wire-format version of the job document and the check-in protocol.
pub const PROTOCOL_VERSION: u32 = 1;

/// An affine point as two hex strings (no `0x` prefix).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct HexPoint {
    pub x: String,
    pub y: String,
}

impl HexPoint {
    pub fn from_point(p: &Point) -> Option<Self> {
        match p {
            Point::Infinity => None,
            Point::Affine { x, y } => Some(Self {
                x: hex_of(&x.value),
                y: hex_of(&y.value),
            }),
        }
    }

    pub fn to_point(&self, p: &BigUint) -> Result<Point, String> {
        Ok(Point::Affine {
            x: FieldElement::new(parse_hex(&self.x)?, p.clone()),
            y: FieldElement::new(parse_hex(&self.y)?, p.clone()),
        })
    }
}

/// The shared job document.  Every field participates in the job id.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct JobSpec {
    /// Protocol version; peers on a different version refuse the job.
    pub version: u32,
    /// Free-form label (participates in the id, so rename ⇒ new job).
    pub name: String,
    /// Field prime `p` (hex).
    pub p: String,
    /// Curve coefficient `a` (hex).
    pub a: String,
    /// Curve coefficient `b` (hex).
    pub b: String,
    /// Base point `P`.
    pub generator: HexPoint,
    /// Target `Q = x·P`; the job's goal is `x`.
    pub target: HexPoint,
    /// Prime order `n` of `⟨P⟩` (hex).
    pub order: String,
    /// A point is distinguished when the low `dp_bits` bits of its
    /// x-coordinate are zero.  Mean trail length `2^dp_bits`.
    pub dp_bits: u8,
    /// Number of `r`-adding branches.  16–32 is the usual choice.
    pub num_branches: u32,
    /// Fold each step to the `±` representative (x-only DP keys),
    /// halving the effective group size at the cost of fruitless
    /// cycles that the per-walker step cap escapes.
    pub negation_map: bool,
    /// Walkers per work unit.  A unit is the granule of claiming,
    /// leasing and progress reporting.
    pub unit_size: u64,
    /// Steps after which a walker is abandoned as a dead trail; `0`
    /// selects `20 · 2^dp_bits`.
    pub max_steps_per_walker: u64,
    /// Domain-separation seed mixed into every PRF derivation, so the
    /// same curve and target can be re-run with fresh walks.
    pub seed: u64,
}

impl JobSpec {
    /// Build a job for `target` on `curve` with sensible defaults
    /// (`dp_bits` ≈ ¼·log₂n capped at 20, 32 branches, no negation
    /// map, units of 256 walkers).
    pub fn new(curve: &CurveParams, target: &Point, name: &str, seed: u64) -> Result<Self, String> {
        let bits = curve.n.bits() as u32;
        let dp_bits = (bits / 4).clamp(2, 20) as u8;
        Ok(Self {
            version: PROTOCOL_VERSION,
            name: name.to_string(),
            p: hex_of(&curve.p),
            a: hex_of(&curve.a),
            b: hex_of(&curve.b),
            generator: HexPoint {
                x: hex_of(&curve.gx),
                y: hex_of(&curve.gy),
            },
            target: HexPoint::from_point(target).ok_or("target must not be the identity")?,
            order: hex_of(&curve.n),
            dp_bits,
            num_branches: 32,
            negation_map: false,
            unit_size: 256,
            max_steps_per_walker: 0,
            seed,
        })
    }

    /// Canonical byte encoding hashed into the job id.  Deliberately
    /// *not* the JSON (whitespace / key order would leak in).
    fn canonical_bytes(&self) -> Vec<u8> {
        let mut out = Vec::new();
        let mut push = |tag: &str, v: &str| {
            out.extend_from_slice(tag.as_bytes());
            out.push(b'=');
            out.extend_from_slice(v.to_ascii_lowercase().as_bytes());
            out.push(b'\n');
        };
        push("version", &self.version.to_string());
        push("name", &self.name);
        push("p", &self.p);
        push("a", &self.a);
        push("b", &self.b);
        push("gx", &self.generator.x);
        push("gy", &self.generator.y);
        push("qx", &self.target.x);
        push("qy", &self.target.y);
        push("n", &self.order);
        push("dp_bits", &self.dp_bits.to_string());
        push("branches", &self.num_branches.to_string());
        push("negation", &self.negation_map.to_string());
        push("unit_size", &self.unit_size.to_string());
        push("max_steps", &self.max_steps_per_walker.to_string());
        push("seed", &self.seed.to_string());
        out
    }

    /// SHA-256 of the canonical encoding, hex.
    pub fn job_id(&self) -> String {
        hex::encode(sha256(&self.canonical_bytes()))
    }

    /// Serialise to pretty JSON.
    pub fn to_json(&self) -> String {
        serde_json::to_string_pretty(self).expect("JobSpec serialises")
    }

    /// Parse from JSON.
    pub fn from_json(s: &str) -> Result<Self, String> {
        serde_json::from_str(s).map_err(|e| format!("job JSON: {e}"))
    }

    /// Validate and expand into a runtime [`JobContext`].
    pub fn build(&self) -> Result<JobContext, String> {
        JobContext::new(self.clone())
    }
}

/// One branch of the `r`-adding walk: `point = u·P + v·Q`.
#[derive(Clone, Debug)]
pub struct Branch {
    pub u: BigUint,
    pub v: BigUint,
    pub point: Point,
}

/// Validated, expanded job: curve arithmetic context, branch table,
/// DP mask.  Cheap to clone; share behind an `Arc` across threads.
#[derive(Clone, Debug)]
pub struct JobContext {
    pub spec: JobSpec,
    pub job_id: String,
    pub p: BigUint,
    pub a: FieldElement,
    pub b: BigUint,
    pub n: BigUint,
    pub g: Point,
    pub q: Point,
    pub branches: Vec<Branch>,
    pub dp_mask: BigUint,
    pub step_cap: u64,
}

impl JobContext {
    pub fn new(spec: JobSpec) -> Result<Self, String> {
        if spec.version != PROTOCOL_VERSION {
            return Err(format!(
                "job version {} ≠ supported {}",
                spec.version, PROTOCOL_VERSION
            ));
        }
        let p = parse_hex(&spec.p)?;
        let a_v = parse_hex(&spec.a)?;
        let b = parse_hex(&spec.b)?;
        let n = parse_hex(&spec.order)?;
        if p <= BigUint::from(3u32) {
            return Err("field prime must exceed 3".into());
        }
        if n <= BigUint::one() {
            return Err("group order must be ≥ 2".into());
        }
        if spec.dp_bits >= 64 {
            return Err("dp_bits must be < 64".into());
        }
        if spec.num_branches < 2 {
            return Err("num_branches must be ≥ 2".into());
        }
        if spec.unit_size == 0 {
            return Err("unit_size must be ≥ 1".into());
        }
        let a = FieldElement::new(a_v.clone(), p.clone());
        let g = spec.generator.to_point(&p)?;
        let q = spec.target.to_point(&p)?;
        let curve = CurveParams {
            name: "job",
            p: p.clone(),
            a: a_v,
            b: b.clone(),
            gx: BigUint::zero(),
            gy: BigUint::zero(),
            n: n.clone(),
            h: 1,
        };
        if !curve.is_on_curve(&g) {
            return Err("generator is not on the curve".into());
        }
        if !curve.is_on_curve(&q) {
            return Err("target is not on the curve".into());
        }
        if g.scalar_mul(&n, &a) != Point::Infinity {
            return Err("n·P ≠ ∞: order is wrong".into());
        }
        let job_id = spec.job_id();
        let mut branches = Vec::with_capacity(spec.num_branches as usize);
        for j in 0..spec.num_branches as u64 {
            let u = derive_scalar(&job_id, "branch-u", j, &n);
            let v = derive_scalar(&job_id, "branch-v", j, &n);
            let point = g.scalar_mul(&u, &a).add(&q.scalar_mul(&v, &a), &a);
            branches.push(Branch { u, v, point });
        }
        let dp_mask = (BigUint::one() << spec.dp_bits) - BigUint::one();
        let step_cap = if spec.max_steps_per_walker == 0 {
            20u64 << spec.dp_bits
        } else {
            spec.max_steps_per_walker
        };
        Ok(Self {
            spec,
            job_id,
            p,
            a,
            b,
            n,
            g,
            q,
            branches,
            dp_mask,
            step_cap,
        })
    }

    /// Deterministic start of walker `i`: `(a_i, b_i, a_i·P + b_i·Q)`.
    pub fn walker_start(&self, i: u64) -> (BigUint, BigUint, Point) {
        let a = derive_scalar(&self.job_id, "walker-a", i, &self.n);
        let b = derive_scalar(&self.job_id, "walker-b", i, &self.n);
        let r = self
            .g
            .scalar_mul(&a, &self.a)
            .add(&self.q.scalar_mul(&b, &self.a), &self.a);
        (a, b, r)
    }

    /// Work unit `u` covers walker indices `[first, last)`.
    pub fn unit_range(&self, unit: u64) -> (u64, u64) {
        let first = unit.saturating_mul(self.spec.unit_size);
        let last = first.saturating_add(self.spec.unit_size);
        (first, last)
    }

    /// `a·P + b·Q` — used to verify a claimed distinguished point.
    pub fn combine(&self, a: &BigUint, b: &BigUint) -> Point {
        self.g
            .scalar_mul(a, &self.a)
            .add(&self.q.scalar_mul(b, &self.a), &self.a)
    }

    /// Is `pt` on the job's curve?
    pub fn on_curve(&self, pt: &Point) -> bool {
        match pt {
            Point::Infinity => true,
            Point::Affine { x, y } => {
                if x.modulus != self.p || y.modulus != self.p {
                    return false;
                }
                let lhs = (&y.value * &y.value) % &self.p;
                let rhs =
                    (&x.value * &x.value * &x.value + &self.a.value * &x.value + &self.b) % &self.p;
                lhs == rhs
            }
        }
    }

    /// Distinguished-point predicate: low `dp_bits` of `x` are zero.
    pub fn is_dp(&self, pt: &Point) -> bool {
        match pt {
            Point::Affine { x, .. } => (&x.value & &self.dp_mask).is_zero(),
            Point::Infinity => false,
        }
    }

    /// Table key of a DP: `x` alone under the negation map (±P share
    /// a key), else `x:y`.
    pub fn dp_key(&self, pt: &Point) -> String {
        match pt {
            Point::Infinity => String::from("inf"),
            Point::Affine { x, y } => {
                if self.spec.negation_map {
                    hex_of(&x.value)
                } else {
                    format!("{}:{}", hex_of(&x.value), hex_of(&y.value))
                }
            }
        }
    }

    /// Expected group operations for one rho solve: `√(πn/2)`, divided
    /// by `√2` under the negation map.  Used only for progress
    /// reporting.
    pub fn expected_steps(&self) -> f64 {
        let n = biguint_to_f64(&self.n);
        let base = (std::f64::consts::PI * n / 2.0).sqrt();
        if self.spec.negation_map {
            base / std::f64::consts::SQRT_2
        } else {
            base
        }
    }

    /// Expected number of distinguished points before the solving
    /// collision: `expected_steps / 2^dp_bits`.
    pub fn expected_dps(&self) -> f64 {
        self.expected_steps() / (1u64 << self.spec.dp_bits) as f64
    }
}

/// `PRF(job_id, tag, idx) mod n` from two SHA-256 blocks (512 bits of
/// entropy before reduction, so the bias is negligible for any `n`
/// this code will meet).
pub(crate) fn derive_scalar(job_id: &str, tag: &str, idx: u64, n: &BigUint) -> BigUint {
    let mut wide = Vec::with_capacity(64);
    for ctr in 0u8..2 {
        let mut buf = Vec::with_capacity(job_id.len() + tag.len() + 10);
        buf.extend_from_slice(job_id.as_bytes());
        buf.push(0);
        buf.extend_from_slice(tag.as_bytes());
        buf.push(0);
        buf.extend_from_slice(&idx.to_be_bytes());
        buf.push(ctr);
        wide.extend_from_slice(&sha256(&buf));
    }
    BigUint::from_bytes_be(&wide) % n
}

pub(crate) fn hex_of(v: &BigUint) -> String {
    v.to_str_radix(16)
}

pub(crate) fn parse_hex(s: &str) -> Result<BigUint, String> {
    let t = s.trim().trim_start_matches("0x");
    if t.is_empty() {
        return Err("empty hex scalar".into());
    }
    BigUint::parse_bytes(t.as_bytes(), 16).ok_or_else(|| format!("bad hex scalar `{s}`"))
}

pub(crate) fn biguint_to_f64(n: &BigUint) -> f64 {
    let bits = n.bits();
    if bits <= 52 {
        return n.iter_u64_digits().next().unwrap_or(0) as f64;
    }
    let shift = bits - 52;
    let top = (n >> shift).iter_u64_digits().next().unwrap_or(0) as f64;
    top * 2f64.powi(shift as i32)
}

// ── Demo curves ──────────────────────────────────────────────────────────────

/// Built-in curves for the CLI and tests.
///
/// | name | field | order | `√n` |
/// |------|-------|-------|------|
/// | `demo-small` | 10007 | 10039 | ≈100 |
/// | `demo-mid` | 99013 | 98893 | ≈314 |
/// | `demo-32` | 32-bit prime | 32-bit prime | ≈2¹⁶ — seconds on one core |
/// | `demo-40` | 40-bit prime | 40-bit prime | ≈2²⁰ — minutes on one core; the collaboration demo |
/// | `secp256k1` | 256-bit | 256-bit | hopeless — for job-format demos |
///
/// The 32/40-bit curves were generated with the random-curve search
/// in `examples/eccp79_rho.rs` (random `a, b`, order by BSGS over the
/// Hasse interval, Miller–Rabin on the order); [`JobContext::new`]
/// re-checks `n·P = ∞` every time one is used.
pub fn demo_curve(name: &str) -> Option<CurveParams> {
    let hx = |s: &str| BigUint::parse_bytes(s.as_bytes(), 16).expect("static hex");
    match name {
        "demo-32" => Some(CurveParams {
            name: "demo-32",
            p: hx("b870782f"),
            a: hx("2448f190"),
            b: hx("7dbde112"),
            gx: hx("8ea8c2a4"),
            gy: hx("64fa5d9f"),
            n: hx("b8720457"),
            h: 1,
        }),
        "demo-40" => Some(CurveParams {
            name: "demo-40",
            p: hx("fb520b9a55"),
            a: hx("e52c4a04b1"),
            b: hx("cd5eb45d37"),
            gx: hx("59bef2d04a"),
            gy: hx("f6af895239"),
            n: hx("fb5219301b"),
            h: 1,
        }),
        "demo-small" => Some(CurveParams {
            name: "demo-10007",
            p: BigUint::from(10_007u32),
            a: BigUint::from(3u32),
            b: BigUint::from(6u32),
            gx: BigUint::zero(),
            gy: BigUint::from(1973u32),
            n: BigUint::from(10_039u32),
            h: 1,
        }),
        "demo-mid" => Some(CurveParams {
            name: "demo-99013",
            p: BigUint::from(99_013u32),
            a: BigUint::from(6u32),
            b: BigUint::from(4u32),
            gx: BigUint::zero(),
            gy: BigUint::from(2u32),
            n: BigUint::from(98_893u32),
            h: 1,
        }),
        "secp256k1" => Some(CurveParams::secp256k1()),
        _ => None,
    }
}

/// Names accepted by [`demo_curve`].
pub const DEMO_CURVES: &[&str] = &["demo-small", "demo-mid", "demo-32", "demo-40", "secp256k1"];

#[cfg(test)]
mod tests {
    use super::*;

    fn mid_job() -> (CurveParams, JobSpec, BigUint) {
        let curve = demo_curve("demo-mid").unwrap();
        let x = BigUint::from(73_313u32);
        let q = curve.generator().scalar_mul(&x, &curve.a_fe());
        let spec = JobSpec::new(&curve, &q, "t", 7).unwrap();
        (curve, spec, x)
    }

    #[test]
    fn job_id_is_stable_and_field_sensitive() {
        let (_, spec, _) = mid_job();
        let id1 = spec.job_id();
        let round = JobSpec::from_json(&spec.to_json()).unwrap();
        assert_eq!(round, spec);
        assert_eq!(round.job_id(), id1);
        let mut other = spec.clone();
        other.seed += 1;
        assert_ne!(other.job_id(), id1);
        let mut other = spec.clone();
        other.dp_bits += 1;
        assert_ne!(other.job_id(), id1);
        // Upper/lower-case hex encode the same job.
        let mut other = spec.clone();
        other.order = other.order.to_uppercase();
        assert_eq!(other.job_id(), id1);
    }

    #[test]
    fn context_validates_inputs() {
        let (_, spec, _) = mid_job();
        assert!(spec.build().is_ok());
        let mut bad = spec.clone();
        bad.target.x = "1".into();
        assert!(bad.build().unwrap_err().contains("target"));
        let mut bad = spec.clone();
        bad.order = "1234".into();
        assert!(bad.build().unwrap_err().contains("order"));
        let mut bad = spec.clone();
        bad.version = 99;
        assert!(bad.build().is_err());
    }

    #[test]
    fn derivations_are_deterministic_and_on_curve() {
        let (_, spec, _) = mid_job();
        let c1 = spec.build().unwrap();
        let c2 = spec.build().unwrap();
        for j in 0..c1.branches.len() {
            assert_eq!(c1.branches[j].point, c2.branches[j].point);
            assert!(c1.on_curve(&c1.branches[j].point));
            assert_eq!(
                c1.branches[j].point,
                c1.combine(&c1.branches[j].u, &c1.branches[j].v)
            );
        }
        for i in [0u64, 1, 255, 1 << 40] {
            let (a, b, r) = c1.walker_start(i);
            assert_eq!(c2.walker_start(i), (a.clone(), b.clone(), r.clone()));
            assert_eq!(c1.combine(&a, &b), r);
        }
        assert_ne!(c1.walker_start(0).2, c1.walker_start(1).2);
    }

    #[test]
    fn every_demo_curve_builds_a_job() {
        // secp256k1 is skipped: 65 scalar multiplications at 256 bits
        // take most of a minute in a debug build.
        for name in DEMO_CURVES.iter().filter(|n| **n != "secp256k1") {
            let curve = demo_curve(name).unwrap();
            let q = curve
                .generator()
                .scalar_mul(&BigUint::from(12_345u32), &curve.a_fe());
            let spec = JobSpec::new(&curve, &q, name, 0).unwrap();
            let ctx = spec.build().unwrap_or_else(|e| panic!("{name}: {e}"));
            assert_eq!(ctx.g, curve.generator());
        }
        assert!(demo_curve("nope").is_none());
    }

    #[test]
    fn unit_ranges_partition_index_space() {
        let (_, spec, _) = mid_job();
        let ctx = spec.build().unwrap();
        assert_eq!(ctx.unit_range(0), (0, 256));
        assert_eq!(ctx.unit_range(3), (768, 1024));
    }

    #[test]
    fn expected_cost_matches_sqrt_scale() {
        let (_, spec, _) = mid_job();
        let ctx = spec.build().unwrap();
        // √(π·98893/2) ≈ 394
        assert!((ctx.expected_steps() - 394.1).abs() < 2.0);
        assert!(biguint_to_f64(&(BigUint::one() << 100)) > 1e30);
    }
}
