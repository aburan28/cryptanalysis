//! Resumable, full-subgroup signed-Frobenius rho for the pinned cover image.
//! This is a separately named experiment, not the registered ecbench method.
use crate::checks::{element, native_point};
use crate::cryptanalysis::koblitz_strong_rho::{
    RawPointG, RhoScalar, StrongRhoCharges, StrongRhoParams, WalkStateG, WideStrongRho, JUMPS,
};
use crate::cryptanalysis::wide_gf2m::WideGf2;
use crate::{GenusTwoCover, Result};
use curve_backend::binary_ecc::{BinaryPoint, IrreduciblePoly, MumfordDivisor};
use ecdlp_surfaces::binary::{n83_fixture, BinaryPoint as FixturePoint};
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;
use std::time::Instant;
use surface_evidence::hash::sha256::sha256;

pub const METHOD: &str = "rho.cover_image_checkpoint/v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash, Serialize, Deserialize)]
pub enum Point {
    O,
    A { x: u128, y: u128 },
}
impl From<RawPointG<u128>> for Point {
    fn from(p: RawPointG<u128>) -> Self {
        match p {
            RawPointG::Infinity => Self::O,
            RawPointG::Affine { x, y } => Self::A { x, y },
        }
    }
}
impl From<Point> for RawPointG<u128> {
    fn from(p: Point) -> Self {
        match p {
            Point::O => Self::Infinity,
            Point::A { x, y } => Self::Affine { x, y },
        }
    }
}
impl Point {
    pub fn binary(self) -> BinaryPoint {
        match self {
            Self::O => BinaryPoint::Infinity,
            Self::A { x, y } => native_point(FixturePoint::Affine(x, y), 83),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Job {
    pub schema: String,
    pub a: u8,
    pub index: u32,
    pub generator: Point,
    pub target: Point,
    pub order: u128,
    pub jump_seed: u64,
    pub start_seed: u64,
    pub lanes: usize,
    pub dp_bits: u32,
}
impl Job {
    pub fn hash(&self) -> Result<String> {
        Ok(hex_digest(
            &serde_json::to_vec(self).map_err(|e| e.to_string())?,
        ))
    }
}

fn mul(a: u128, b: u128, r: u128) -> u128 {
    <u128 as RhoScalar>::mul_mod(a, b, r)
}
fn add(a: u128, b: u128, r: u128) -> u128 {
    <u128 as RhoScalar>::add_mod(a, b, r)
}
fn sub(a: u128, b: u128, r: u128) -> u128 {
    <u128 as RhoScalar>::sub_mod(a, b, r)
}
fn pow(mut a: u128, mut e: u128, r: u128) -> u128 {
    let mut out = 1;
    while e != 0 {
        if e & 1 != 0 {
            out = mul(out, a, r);
        }
        a = mul(a, a, r);
        e >>= 1;
    }
    out
}
fn sqrt_mod(v: u128, r: u128) -> Result<u128> {
    if pow(v, (r - 1) / 2, r) != 1 {
        return Err("Frobenius discriminant is not a square".into());
    }
    let mut z = 2;
    while pow(z, (r - 1) / 2, r) != r - 1 {
        z += 1;
    }
    let mut m = (r - 1).trailing_zeros();
    let q = (r - 1) >> m;
    let (mut c, mut t, mut x) = (pow(z, q, r), pow(v, q, r), pow(v, q.div_ceil(2), r));
    while t != 1 {
        let (mut t2, mut i) = (t, 0);
        while t2 != 1 && i < m {
            t2 = mul(t2, t2, r);
            i += 1;
        }
        if i >= m {
            return Err("Tonelli-Shanks failed".into());
        }
        let b = pow(c, 1_u128 << (m - i - 1), r);
        x = mul(x, b, r);
        c = mul(b, b, r);
        t = mul(t, c, r);
        m = i;
    }
    Ok(x)
}

pub struct Context {
    pub job: Job,
    pub rho: WideStrongRho,
    pub cover: GenusTwoCover,
    pub jumps: Vec<(Point, u128)>,
    pub jac_jumps: Vec<MumfordDivisor>,
    pub setup_seconds: f64,
    pub setup_counts: BTreeMap<String, u64>,
}
impl Context {
    pub fn new(job: Job, jacobian: bool) -> Result<Self> {
        let timer = Instant::now();
        let fixture = n83_fixture(job.a)?;
        let expected_g = Point::from(RawPointG::from_binary_wide(&native_point(
            fixture.generator,
            83,
        )));
        if job.schema != "cover-rho.public-job/v1"
            || job.order != fixture.subgroup_order
            || job.generator != expected_g
            || job.target == Point::O
            || job.dp_bits == 0
            || job.dp_bits > 24
            || job.lanes == 0
            || job.lanes > 128
        {
            return Err("invalid public job or unsupported parameters".into());
        }
        let irr = IrreduciblePoly {
            degree: 83,
            low_terms: vec![45, 2, 1, 0],
        };
        let cover = GenusTwoCover::new(83, irr.clone(), element(u128::from(job.a), 83))?;
        if !cover.target_contains(&job.target.binary()) {
            return Err("target is off curve".into());
        }
        let gf = WideGf2::new(&irr);
        let g = RawPointG::from(job.generator);
        let raw = WideStrongRho::from_parts_unchecked(gf.clone(), job.a.into(), job.order, g);
        if raw.scalar_mul(job.target.into(), job.order) != RawPointG::Infinity {
            return Err("target is outside the selected subgroup".into());
        }
        let t = if job.a == 0 { job.order - 1 } else { 1 };
        let d = sqrt_mod(sub(mul(t, t, job.order), 8, job.order), job.order)?;
        let root = mul(add(t, d, job.order), job.order.div_ceil(2), job.order);
        let frob = match job.generator {
            Point::A { x, y } => RawPointG::Affine {
                x: gf.sqr(x),
                y: gf.sqr(y),
            },
            Point::O => return Err("zero generator".into()),
        };
        let lambda = if raw.scalar_mul(g, root) == frob {
            root
        } else {
            sub(t, root, job.order)
        };
        if raw.scalar_mul(g, lambda) != frob {
            return Err("Frobenius eigenvalue did not verify".into());
        }
        let rho = WideStrongRho::from_parts(gf, job.a.into(), job.order, lambda, g);
        if rho.automorphisms() != 166 {
            return Err("unexpected signed-Frobenius orbit size".into());
        }
        let mut charges = StrongRhoCharges::default();
        let jumps: Vec<(Point, u128)> = rho
            .jumps(job.jump_seed, &mut charges)
            .into_iter()
            .map(|j| (j.point.into(), j.a))
            .collect();
        let jac_jumps = if jacobian {
            jumps
                .iter()
                .map(|(p, _)| cover.pullback(&p.binary()))
                .collect::<Result<Vec<_>>>()?
        } else {
            Vec::new()
        };
        let setup_seconds = timer.elapsed().as_secs_f64();
        let setup_counts = BTreeMap::from([
            (
                "jump_scalar_multiplications".into(),
                charges.scalar_multiplications,
            ),
            ("target_subgroup_scalar_multiplications".into(), 1),
            ("frobenius_eigenvalue_scalar_multiplications".into(), 2),
            ("jacobian_jump_pullbacks".into(), jac_jumps.len() as u64),
        ]);
        Ok(Self {
            job,
            rho,
            cover,
            jumps,
            jac_jumps,
            setup_seconds,
            setup_counts,
        })
    }
    fn canonical(
        &self,
        p: Point,
        a: u128,
        b: u128,
        counts: &mut BTreeMap<String, u64>,
    ) -> (Point, u128, u128) {
        count(counts, "canonicalizations", 1);
        let s = self.rho.canonicalize(WalkStateG {
            point: p.into(),
            a,
            b,
        });
        (s.point.into(), s.a, s.b)
    }
    fn native_add(&self, p: Point, q: Point, counts: &mut BTreeMap<String, u64>) -> Point {
        count(counts, "elliptic_additions", 1);
        self.rho.add(p.into(), q.into()).into()
    }
    pub fn verify(&self, scalar: u128) -> Result<Value> {
        let timer = Instant::now();
        if scalar >= self.job.order
            || Point::from(self.rho.scalar_mul(self.job.generator.into(), scalar))
                != self.job.target
        {
            return Err("recovered scalar failed elliptic verification".into());
        }
        let dp = self.cover.pullback(&self.job.generator.binary())?;
        let dq = self.cover.pullback(&self.job.target.binary())?;
        if dp
            .try_scalar_mul(&BigUint::from(scalar), self.cover.source())
            .map_err(|e| e.to_string())?
            != dq
        {
            return Err("recovered scalar failed native Jacobian verification".into());
        }
        Ok(
            json!({"schema":"cover-rho.verification/v1", "job_sha256": self.job.hash()?,
            "scalar":scalar.to_string(), "elliptic_verified":true, "jacobian_verified":true,
            "wall_seconds":timer.elapsed().as_secs_f64(),
            "native_work":{"elliptic_scalar_multiplications":1,"jacobian_scalar_multiplications":1,"pullbacks":2}}),
        )
    }
}

pub fn count(c: &mut BTreeMap<String, u64>, name: &str, n: u64) {
    *c.entry(name.to_owned()).or_default() += n;
}
pub fn hex_digest(bytes: &[u8]) -> String {
    sha256(bytes).iter().map(|b| format!("{b:02x}")).collect()
}
fn fold(x: u128) -> u64 {
    (x as u64) ^ ((x >> 64) as u64).rotate_left(29)
}
fn xy(p: Point) -> (u64, u64) {
    match p {
        Point::O => (0, 0),
        Point::A { x, y } => (fold(x), fold(y)),
    }
}
fn partition(p: Point) -> usize {
    let (x, y) = xy(p);
    let mut v = x ^ y.rotate_left(21) ^ 0x9e37_79b9_7f4a_7c15;
    v ^= v >> 30;
    v = v.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    v ^= v >> 27;
    v = v.wrapping_mul(0x94d0_49bb_1331_11eb);
    ((v ^ (v >> 31)) as usize) % JUMPS
}
fn dp_hash(p: Point) -> u64 {
    let (x, y) = xy(p);
    let mut v = x.rotate_left(7) ^ y ^ 0x2545_f491_4f6c_dd1d;
    v ^= v >> 33;
    v = v.wrapping_mul(0xff51_afd7_ed55_8ccd);
    v ^= v >> 33;
    v = v.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    v ^ (v >> 33)
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Lane {
    pub point: Point,
    pub a: u128,
    pub b: u128,
    pub previous: [Point; 4],
    pub length: u64,
    pub live: bool,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Hit {
    pub point: Point,
    pub a: u128,
    pub b: u128,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Checkpoint {
    pub schema: String,
    pub method: String,
    pub job_sha256: String,
    pub arm: String,
    pub steps: u64,
    pub rounds: u64,
    pub walks: u64,
    pub counts: BTreeMap<String, u64>,
    pub stride_a: u128,
    pub stride: Point,
    pub cursor_a: u128,
    pub cursor: Point,
    pub lanes: Vec<Lane>,
    pub table: Vec<Hit>,
    pub candidate: Option<u128>,
    pub setup_seconds: f64,
    pub setup_counts: BTreeMap<String, u64>,
    pub search_seconds: f64,
    pub checkpoint_seconds: f64,
    pub resume_seconds: f64,
    pub resumes: u64,
}
impl Checkpoint {
    pub fn new(ctx: &Context, arm: &str) -> Result<Self> {
        if arm != "elliptic" && arm != "jacobian" && arm != "image_inverse" {
            return Err("arm must be elliptic, jacobian or image_inverse".into());
        }
        let mut counts = BTreeMap::new();
        let mut rng = StdRng::seed_from_u64(ctx.job.start_seed);
        let stride_a = rng.gen_range(1..ctx.job.order);
        let cursor_a = rng.gen_range(0..ctx.job.order);
        let timer = Instant::now();
        let stride = ctx
            .rho
            .scalar_mul(ctx.job.generator.into(), stride_a)
            .into();
        let cursor = ctx
            .rho
            .add(
                ctx.rho.scalar_mul(ctx.job.generator.into(), cursor_a),
                ctx.job.target.into(),
            )
            .into();
        count(&mut counts, "elliptic_setup_scalar_multiplications", 2);
        count(&mut counts, "elliptic_setup_additions", 1);
        if arm == "image_inverse" {
            for p in [ctx.job.generator, ctx.job.target] {
                let d = ctx.cover.pullback(&p.binary())?;
                if ctx.cover.inverse_on_image(&d)? != p.binary() {
                    return Err("image inverse mismatch".into());
                }
                count(&mut counts, "setup_pullbacks", 1);
                count(&mut counts, "setup_checked_image_inverses", 1);
            }
        }
        Ok(Self {
            schema: "cover-rho.checkpoint/v1".into(),
            method: METHOD.into(),
            job_sha256: ctx.job.hash()?,
            arm: arm.into(),
            steps: 0,
            rounds: 0,
            walks: 0,
            counts,
            stride_a,
            stride,
            cursor_a,
            cursor,
            lanes: vec![
                Lane {
                    point: Point::O,
                    a: 0,
                    b: 0,
                    previous: [Point::O; 4],
                    length: 0,
                    live: false
                };
                ctx.job.lanes
            ],
            table: Vec::new(),
            candidate: None,
            setup_seconds: ctx.setup_seconds + timer.elapsed().as_secs_f64(),
            setup_counts: ctx.setup_counts.clone(),
            search_seconds: 0.,
            checkpoint_seconds: 0.,
            resume_seconds: 0.,
            resumes: 0,
        })
    }
    pub fn validate(&self, ctx: &Context, arm: &str) -> Result<()> {
        if self.schema != "cover-rho.checkpoint/v1"
            || self.method != METHOD
            || self.job_sha256 != ctx.job.hash()?
            || self.arm != arm
            || self.lanes.len() != ctx.job.lanes
        {
            return Err("checkpoint identity mismatch".into());
        }
        let r = ctx.job.order;
        if self.stride_a == 0
            || self.stride_a >= r
            || self.cursor_a >= r
            || self.lanes.iter().any(|l| l.a >= r || l.b >= r)
            || self.table.iter().any(|h| h.a >= r || h.b >= r)
        {
            return Err("checkpoint coefficient outside subgroup".into());
        }
        // A checkpoint is trusted local state, not an authenticated certificate.
        // Validate lane invariants; replay is the separate integrity check.
        for l in self.lanes.iter().filter(|l| l.live) {
            let p = ctx.rho.add(
                ctx.rho.scalar_mul(ctx.job.generator.into(), l.a),
                ctx.rho.scalar_mul(ctx.job.target.into(), l.b),
            );
            if Point::from(p) != l.point {
                return Err("checkpoint lane invariant failed".into());
            }
        }
        Ok(())
    }
}

pub struct Search {
    pub state: Checkpoint,
    index: HashMap<Point, usize>,
    divisors: Vec<Option<MumfordDivisor>>,
}
impl Search {
    pub fn from_state(ctx: &Context, state: Checkpoint) -> Result<Self> {
        state.validate(ctx, &state.arm)?;
        let index = state
            .table
            .iter()
            .enumerate()
            .map(|(i, h)| (h.point, i))
            .collect();
        let divisors = state
            .lanes
            .iter()
            .map(|l| {
                if state.arm == "jacobian" && l.live {
                    ctx.cover.pullback(&l.point.binary()).map(Some)
                } else {
                    Ok(None)
                }
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(Self {
            state,
            index,
            divisors,
        })
    }
    /// Advance by exactly `budget` lockstep rounds, unless a collision solves.
    /// Round boundaries are checkpoint boundaries, independent of live lanes.
    pub fn advance(&mut self, ctx: &Context, budget: u64) -> Result<()> {
        let begin = Instant::now();
        let stop = self.state.rounds.saturating_add(budget);
        let jac = self.state.arm == "jacobian";
        let r = ctx.job.order;
        while self.state.rounds < stop && self.state.candidate.is_none() {
            self.state.rounds += 1;
            for i in 0..self.state.lanes.len() {
                if !self.state.lanes[i].live {
                    loop {
                        self.state.walks += 1;
                        let start = self.state.cursor;
                        let start_a = self.state.cursor_a;
                        self.state.cursor = ctx.native_add(
                            self.state.cursor,
                            self.state.stride,
                            &mut self.state.counts,
                        );
                        self.state.cursor_a = add(self.state.cursor_a, self.state.stride_a, r);
                        if start == Point::O {
                            continue;
                        }
                        let (point, a, b) =
                            ctx.canonical(start, start_a, 1, &mut self.state.counts);
                        self.state.lanes[i] = Lane {
                            point,
                            a,
                            b,
                            previous: [Point::O; 4],
                            length: 0,
                            live: true,
                        };
                        if jac {
                            self.divisors[i] = Some(ctx.cover.pullback(&point.binary())?);
                            count(&mut self.state.counts, "walk_start_pullbacks", 1);
                        }
                        break;
                    }
                }
            }
            for i in 0..self.state.lanes.len() {
                let l = &mut self.state.lanes[i];
                count(&mut self.state.counts, "dp_hashes", 1);
                if dp_hash(l.point) & ((1_u64 << ctx.job.dp_bits) - 1) != 0 {
                    continue;
                }
                l.live = false;
                count(&mut self.state.counts, "table_queries", 1);
                if let Some(&hit) = self.index.get(&l.point) {
                    let h = &self.state.table[hit];
                    let den = sub(l.b, h.b, r);
                    count(&mut self.state.counts, "collision_modular_inverses", 1);
                    if let Some(inv) = <u128 as RhoScalar>::inverse_mod(den, r) {
                        self.state.candidate = Some(mul(sub(h.a, l.a, r), inv, r));
                        break;
                    }
                    count(&mut self.state.counts, "uninformative_collisions", 1);
                } else {
                    self.index.insert(l.point, self.state.table.len());
                    self.state.table.push(Hit {
                        point: l.point,
                        a: l.a,
                        b: l.b,
                    });
                    count(&mut self.state.counts, "table_inserts", 1);
                }
            }
            if self.state.candidate.is_some() {
                break;
            }
            for i in 0..self.state.lanes.len() {
                let l = &mut self.state.lanes[i];
                if !l.live {
                    continue;
                }
                let ji = partition(l.point);
                count(&mut self.state.counts, "partition_hashes", 1);
                let sum = if jac {
                    let d = self.divisors[i]
                        .as_ref()
                        .ok_or("missing native lane divisor")?
                        .try_add(&ctx.jac_jumps[ji], ctx.cover.source())
                        .map_err(|e| e.to_string())?;
                    count(&mut self.state.counts, "jacobian_checked_additions", 1);
                    let p = ctx.cover.inverse_on_image(&d)?;
                    count(&mut self.state.counts, "checked_image_inverses", 1);
                    Point::from(RawPointG::from_binary_wide(&p))
                } else {
                    ctx.native_add(l.point, ctx.jumps[ji].0, &mut self.state.counts)
                };
                let (mut point, mut a, mut b) = ctx.canonical(
                    sum,
                    add(l.a, ctx.jumps[ji].1, r),
                    l.b,
                    &mut self.state.counts,
                );
                self.state.steps += 1;
                l.length += 1;
                if point == l.point || l.previous.contains(&point) {
                    count(&mut self.state.counts, "cycle_escapes", 1);
                    let double = if jac {
                        let d = ctx.cover.pullback(&point.binary())?;
                        count(&mut self.state.counts, "canonical_pullbacks", 1);
                        let dd = d
                            .try_add(&d, ctx.cover.source())
                            .map_err(|e| e.to_string())?;
                        count(&mut self.state.counts, "jacobian_checked_additions", 1);
                        let p = ctx.cover.inverse_on_image(&dd)?;
                        count(&mut self.state.counts, "checked_image_inverses", 1);
                        Point::from(RawPointG::from_binary_wide(&p))
                    } else {
                        ctx.native_add(point, point, &mut self.state.counts)
                    };
                    (point, a, b) =
                        ctx.canonical(double, add(a, a, r), add(b, b, r), &mut self.state.counts);
                    l.previous = [Point::O; 4];
                } else {
                    l.previous = [l.point, l.previous[0], l.previous[1], l.previous[2]];
                }
                if l.length > (8_u64 << ctx.job.dp_bits) {
                    l.live = false;
                    count(&mut self.state.counts, "capped_walks", 1);
                }
                l.point = point;
                l.a = a;
                l.b = b;
                if jac && l.live {
                    self.divisors[i] = Some(ctx.cover.pullback(&point.binary())?);
                    count(&mut self.state.counts, "canonical_pullbacks", 1);
                }
            }
        }
        self.state.search_seconds += begin.elapsed().as_secs_f64();
        Ok(())
    }
    pub fn write(&mut self, path: &Path) -> Result<()> {
        let t = Instant::now();
        atomic_json(path, &self.state)?;
        self.state.checkpoint_seconds += t.elapsed().as_secs_f64();
        Ok(())
    }
}

pub fn atomic_json<T: Serialize>(path: &Path, value: &T) -> Result<()> {
    let tmp = path.with_extension("json.tmp");
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(&tmp)
        .map_err(|e| e.to_string())?;
    serde_json::to_writer(&mut file, value).map_err(|e| e.to_string())?;
    file.write_all(b"\n").map_err(|e| e.to_string())?;
    file.sync_all().map_err(|e| e.to_string())?;
    fs::rename(&tmp, path).map_err(|e| e.to_string())?;
    if let Some(parent) = path.parent() {
        fs::File::open(parent)
            .and_then(|f| f.sync_all())
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}
pub fn read_json<T: for<'de> Deserialize<'de>>(p: &Path) -> Result<T> {
    serde_json::from_slice(&fs::read(p).map_err(|e| e.to_string())?).map_err(|e| e.to_string())
}

/// OS rejection sampling; this function is used by target generation only.
fn fresh_scalar(r: u128) -> Result<u128> {
    let bits = 128 - (r - 1).leading_zeros();
    let mask = (1_u128 << bits) - 1;
    let mut os = fs::File::open("/dev/urandom").map_err(|e| e.to_string())?;
    loop {
        let mut bytes = [0_u8; 16];
        os.read_exact(&mut bytes).map_err(|e| e.to_string())?;
        let k = u128::from_le_bytes(bytes) & mask;
        if k > 0 && k < r {
            return Ok(k);
        }
    }
}
pub fn generate(public: &Path, witness: &Path) -> Result<()> {
    if public.exists() || witness.exists() {
        return Err("fresh input and witness paths required".into());
    }
    fs::create_dir_all(public).map_err(|e| e.to_string())?;
    let mut heldout = Vec::new();
    for a in 0..=1 {
        let f = n83_fixture(a)?;
        for index in 0..8 {
            let k = fresh_scalar(f.subgroup_order)?;
            let q = f.curve.multiply(k, f.generator)?;
            let job = Job {
                schema: "cover-rho.public-job/v1".into(),
                a,
                index,
                generator: RawPointG::from_binary_wide(&native_point(f.generator, 83)).into(),
                target: RawPointG::from_binary_wide(&native_point(q, 83)).into(),
                order: f.subgroup_order,
                jump_seed: 0x83c0_2026_1014 + u64::from(a) * 100 + u64::from(index),
                start_seed: 0x83c1_2026_1014 + u64::from(a) * 100 + u64::from(index),
                lanes: 32,
                dp_bits: if a == 0 { 16 } else { 8 },
            };
            atomic_json(&public.join(format!("a{a}-{index}.json")), &job)?;
            heldout
                .push(json!({"a":a,"index":index,"job_sha256":job.hash()?,"scalar":k.to_string()}));
        }
    }
    atomic_json(
        witness,
        &json!({"schema":"cover-rho.heldout-witness/v1","targets":heldout}),
    )?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(witness, fs::Permissions::from_mode(0o600))
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn strong_reference(ctx: &Context) -> Result<Value> {
    let t = Instant::now();
    let mut charges = StrongRhoCharges::default();
    let jumps = ctx.rho.jumps(ctx.job.jump_seed, &mut charges);
    let mut rng = StdRng::seed_from_u64(ctx.job.start_seed);
    let p = StrongRhoParams {
        lanes: ctx.job.lanes,
        dp_bits: ctx.job.dp_bits,
        step_cap_factor: 2000,
        escape_fruitless: true,
    };
    let outcome = ctx
        .rho
        .solve(ctx.job.target.into(), &jumps, &mut rng, &p, charges);
    let search_seconds = t.elapsed().as_secs_f64();
    match outcome {
        Some(o) => Ok(
            json!({"schema":"cover-rho.strong-reference/v1","status":"candidate","job_sha256":ctx.job.hash()?,
            "scalar":o.scalar.to_string(),"search_seconds":search_seconds,"setup_seconds":ctx.setup_seconds,
            "steps":o.walk_steps,"walks":o.walks,"ideal_steps":o.ideal_steps,"automorphisms":o.automorphisms,
            "table_entries":o.table_entries,"cycle_escapes":o.escapes,"capped_walks":o.capped,
            "charges":{"group_additions":o.charges.group_additions,"scalar_multiplications":o.charges.scalar_multiplications,
                "canonicalizations":o.charges.canonicalizations,"partition_hashes":o.charges.partition_hashes,
                "table_queries":o.charges.table_queries,"table_inserts":o.charges.table_inserts,"failed_collisions":o.charges.failed_collisions},
            "common_priced_work":null,"speedup":null}),
        ),
        None => Ok(
            json!({"schema":"cover-rho.strong-reference/v1","status":"step_cap","job_sha256":ctx.job.hash()?,"search_seconds":search_seconds,"speedup":null}),
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn job(a: u8) -> Job {
        let f = n83_fixture(a).unwrap();
        Job {
            schema: "cover-rho.public-job/v1".into(),
            a,
            index: 0,
            generator: RawPointG::from_binary_wide(&native_point(f.generator, 83)).into(),
            target: RawPointG::from_binary_wide(&native_point(
                f.curve.multiply(37, f.generator).unwrap(),
                83,
            ))
            .into(),
            order: f.subgroup_order,
            jump_seed: 8300,
            start_seed: 8301,
            lanes: 4,
            dp_bits: 3,
        }
    }
    #[test]
    fn pinned_arithmetic_and_frobenius_for_both_subgroups() {
        for a in 0..=1 {
            let ctx = Context::new(job(a), false).unwrap();
            let f = n83_fixture(a).unwrap();
            for k in [0, 1, 2, 37, 101, 0xabc123] {
                let want = RawPointG::from_binary_wide(&native_point(
                    f.curve.multiply(k, f.generator).unwrap(),
                    83,
                ));
                assert_eq!(ctx.rho.scalar_mul(ctx.job.generator.into(), k), want);
            }
            assert_eq!(ctx.rho.automorphisms(), 166);
            assert!(ctx.verify(37).is_ok());
            assert!(ctx.verify(38).is_err());
        }
    }
    #[test]
    fn native_jacobian_walk_and_checkpoint_replay_match() {
        let ctx = Context::new(job(1), true).unwrap();
        let mut e = Search::from_state(&ctx, Checkpoint::new(&ctx, "elliptic").unwrap()).unwrap();
        let mut j = Search::from_state(&ctx, Checkpoint::new(&ctx, "jacobian").unwrap()).unwrap();
        e.advance(&ctx, 64).unwrap();
        j.advance(&ctx, 32).unwrap();
        let serialized = serde_json::to_vec(&j.state).unwrap();
        let mut resumed =
            Search::from_state(&ctx, serde_json::from_slice(&serialized).unwrap()).unwrap();
        resumed.advance(&ctx, 32).unwrap();
        assert_eq!(e.state.steps, resumed.state.steps);
        assert_eq!(e.state.lanes, resumed.state.lanes);
        assert_eq!(e.state.table, resumed.state.table);
        assert_eq!(e.state.candidate, resumed.state.candidate);
        j.advance(&ctx, 32).unwrap();
        assert_eq!(j.state.counts, resumed.state.counts);
        assert!(resumed.state.counts["jacobian_checked_additions"] > 0);
    }
    #[test]
    fn collision_recovers_and_external_verifier_rejects_wrong_scalar() {
        let ctx = Context::new(job(1), false).unwrap();
        let mut s = Search::from_state(&ctx, Checkpoint::new(&ctx, "elliptic").unwrap()).unwrap();
        s.advance(&ctx, 64).unwrap();
        let hit = s.state.table[0].clone();
        let a = add(hit.a, mul(hit.b, 37, ctx.job.order), ctx.job.order);
        s.state.lanes[0] = Lane {
            point: hit.point,
            a,
            b: 0,
            previous: [Point::O; 4],
            length: 0,
            live: true,
        };
        s.advance(&ctx, 4).unwrap();
        assert_eq!(s.state.candidate, Some(37));
        ctx.verify(s.state.candidate.unwrap()).unwrap();
    }
    #[test]
    fn identity_validation_fails_closed() {
        let ctx = Context::new(job(1), false).unwrap();
        let mut s = Checkpoint::new(&ctx, "elliptic").unwrap();
        s.job_sha256 = "wrong".into();
        assert!(Search::from_state(&ctx, s).is_err());
        let mut invalid = job(1);
        invalid.target = Point::A { x: 0, y: 0 };
        assert!(Context::new(invalid, false).is_err());
        let mut invalid = job(1);
        invalid.order -= 1;
        assert!(Context::new(invalid, false).is_err());
        let mut data = serde_json::to_value(job(1)).unwrap();
        data["scalar"] = json!(37);
        assert!(serde_json::from_value::<Job>(data).is_err());
    }
}
