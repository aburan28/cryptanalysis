//! Certified, hard-bounded bielliptic plane-quartic index-calculus diagnostic.
//!
//! `C: v^4=x^3+a*x+b` covers `E: y^2=x^3+a*x+b` by `(x,v)->(x,v^2)`.
//! Line sections give principal divisors relative to `4*R_infinity`.
//! Certificates retain the full quartic section; linear algebra is explicitly
//! performed AFTER the elliptic norm projection. Deck-conjugate points are
//! not identified as divisor classes in the full Jacobian.
//!
//! The field-size gate is part of this API. This is a tiny-field correctness
//! tool, not a general Jacobian DLP backend or a performance implementation.
//! No rho, exhaustive-log oracle, or known target scalar is used as fallback.

use std::collections::{BTreeMap, BTreeSet};

/// Maximum prime modulus accepted by this diagnostic.
pub const MAX_PRIME: u64 = 257;
/// Maximum number of secant-pair trials in a collection.
pub const MAX_PAIR_TRIALS: usize = 65_536;
/// Maximum individual-log shift trials.
pub const MAX_TARGET_SHIFTS: u64 = 512;

/// Exact elliptic point; coordinates must be canonical field elements.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum EcPoint {
    Infinity,
    Affine { x: u64, y: u64 },
}

/// Exact quartic point. Infinity denotes the unique point `(1:0:0)`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum QuarticPoint {
    Infinity,
    Affine { x: u64, v: u64 },
}

/// A normalized homogeneous line `a*X+b*V+c*Z=0`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Line {
    pub a: u64,
    pub b: u64,
    pub c: u64,
}

/// A complete line section, including all intersection multiplicities.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RelationCertificate {
    pub line: Line,
    pub terms: Vec<(QuarticPoint, u8)>,
}

/// Unsupported inputs and exact-verification errors are explicit outcomes.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Error {
    UnsupportedField,
    NoncanonicalCoefficient,
    SingularCurve,
    InvalidPoint,
    InvalidLine,
    InvalidCertificate,
    InvalidBudget,
    NonPrimeGroupOrder,
    InvalidGenerator,
    InconsistentRelations,
    InvalidFactorBaseLog,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for Error {}

fn is_prime(n: u64) -> bool {
    n >= 2
        && (2..)
            .take_while(|d| d * d <= n)
            .all(|d| !n.is_multiple_of(d))
}

fn sub(a: u64, b: u64, p: u64) -> u64 {
    (a + p - b % p) % p
}

fn pow(mut a: u64, mut n: u64, p: u64) -> u64 {
    let mut r = 1;
    while n != 0 {
        if n & 1 != 0 {
            r = r * a % p;
        }
        a = a * a % p;
        n >>= 1;
    }
    r
}

fn trim(poly: &mut Vec<u64>) {
    while poly.len() > 1 && poly.last() == Some(&0) {
        poly.pop();
    }
}

fn divide_root(poly: &[u64], root: u64, p: u64) -> Result<Vec<u64>, Error> {
    if poly.len() < 2 {
        return Err(Error::InvalidCertificate);
    }
    let mut q = vec![0; poly.len() - 1];
    let last = q.len() - 1;
    q[last] = poly[last + 1];
    for i in (0..last).rev() {
        q[i] = (poly[i + 1] + root * q[i + 1]) % p;
    }
    if !(poly[0] + root * q[0]).is_multiple_of(p) {
        return Err(Error::InvalidCertificate);
    }
    trim(&mut q);
    Ok(q)
}

/// Nonsingular bounded elliptic curve and its genus-three quartic cover.
#[derive(Clone, Debug)]
pub struct Cover {
    p: u64,
    a: u64,
    b: u64,
    square_roots: Vec<Vec<u64>>,
}

struct Section {
    poly: Vec<u64>,
    parameter_is_v: bool,
    infinity: u8,
}

impl Cover {
    /// Reject characteristic two/three, composite and oversized fields.
    pub fn new(p: u64, a: u64, b: u64) -> Result<Self, Error> {
        if !(5..=MAX_PRIME).contains(&p) || !is_prime(p) {
            return Err(Error::UnsupportedField);
        }
        if a >= p || b >= p {
            return Err(Error::NoncanonicalCoefficient);
        }
        if (4 * pow(a, 3, p) + 27 * b * b).is_multiple_of(p) {
            return Err(Error::SingularCurve);
        }
        let mut square_roots = vec![Vec::new(); p as usize];
        for v in 0..p {
            square_roots[(v * v % p) as usize].push(v);
        }
        Ok(Self {
            p,
            a,
            b,
            square_roots,
        })
    }

    pub fn modulus(&self) -> u64 {
        self.p
    }

    pub fn coefficients(&self) -> (u64, u64) {
        (self.a, self.b)
    }

    fn rhs(&self, x: u64) -> u64 {
        (pow(x, 3, self.p) + self.a * x + self.b) % self.p
    }

    pub fn contains_ec(&self, point: EcPoint) -> bool {
        match point {
            EcPoint::Infinity => true,
            EcPoint::Affine { x, y } => x < self.p && y < self.p && y * y % self.p == self.rhs(x),
        }
    }

    pub fn contains_quartic(&self, point: QuarticPoint) -> bool {
        match point {
            QuarticPoint::Infinity => true,
            QuarticPoint::Affine { x, v } => {
                x < self.p && v < self.p && pow(v, 4, self.p) == self.rhs(x)
            }
        }
    }

    pub fn image(&self, point: QuarticPoint) -> Result<EcPoint, Error> {
        if !self.contains_quartic(point) {
            return Err(Error::InvalidPoint);
        }
        Ok(match point {
            QuarticPoint::Infinity => EcPoint::Infinity,
            QuarticPoint::Affine { x, v } => EcPoint::Affine {
                x,
                y: v * v % self.p,
            },
        })
    }

    pub fn neg(&self, point: EcPoint) -> Result<EcPoint, Error> {
        if !self.contains_ec(point) {
            return Err(Error::InvalidPoint);
        }
        Ok(match point {
            EcPoint::Infinity => EcPoint::Infinity,
            EcPoint::Affine { x, y } => EcPoint::Affine {
                x,
                y: sub(0, y, self.p),
            },
        })
    }

    fn add_valid(&self, left: EcPoint, right: EcPoint) -> EcPoint {
        let (x, y, u, v) = match (left, right) {
            (EcPoint::Infinity, _) => return right,
            (_, EcPoint::Infinity) => return left,
            (EcPoint::Affine { x, y }, EcPoint::Affine { x: u, y: v }) => (x, y, u, v),
        };
        if x == u && (y + v) % self.p == 0 {
            return EcPoint::Infinity;
        }
        let slope = if left == right {
            (3 * x * x + self.a) % self.p * pow(2 * y % self.p, self.p - 2, self.p) % self.p
        } else {
            sub(v, y, self.p) * pow(sub(u, x, self.p), self.p - 2, self.p) % self.p
        };
        let nx = sub(sub(slope * slope % self.p, x, self.p), u, self.p);
        EcPoint::Affine {
            x: nx,
            y: sub(slope * sub(x, nx, self.p) % self.p, y, self.p),
        }
    }

    pub fn add(&self, left: EcPoint, right: EcPoint) -> Result<EcPoint, Error> {
        if !self.contains_ec(left) || !self.contains_ec(right) {
            return Err(Error::InvalidPoint);
        }
        Ok(self.add_valid(left, right))
    }

    pub fn mul(&self, mut point: EcPoint, mut scalar: u64) -> Result<EcPoint, Error> {
        if !self.contains_ec(point) {
            return Err(Error::InvalidPoint);
        }
        let mut result = EcPoint::Infinity;
        while scalar != 0 {
            if scalar & 1 != 0 {
                result = self.add_valid(result, point);
            }
            point = self.add_valid(point, point);
            scalar >>= 1;
        }
        Ok(result)
    }

    /// Exact order, by tiny-field point enumeration, not a large-field oracle.
    pub fn group_order(&self) -> u64 {
        1 + (0..self.p)
            .map(|x| self.square_roots[self.rhs(x) as usize].len() as u64)
            .sum::<u64>()
    }

    pub fn rational_points(&self) -> Vec<QuarticPoint> {
        let mut fourth = vec![Vec::new(); self.p as usize];
        for v in 0..self.p {
            fourth[pow(v, 4, self.p) as usize].push(v);
        }
        let mut points = vec![QuarticPoint::Infinity];
        for x in 0..self.p {
            for &v in &fourth[self.rhs(x) as usize] {
                points.push(QuarticPoint::Affine { x, v });
            }
        }
        points
    }

    pub fn line(&self, a: u64, b: u64, c: u64) -> Result<Line, Error> {
        if [a, b, c].iter().any(|&x| x >= self.p) {
            return Err(Error::InvalidLine);
        }
        let pivot = [a, b, c]
            .into_iter()
            .find(|&x| x != 0)
            .ok_or(Error::InvalidLine)?;
        let inv = pow(pivot, self.p - 2, self.p);
        Ok(Line {
            a: a * inv % self.p,
            b: b * inv % self.p,
            c: c * inv % self.p,
        })
    }

    pub fn secant(&self, left: QuarticPoint, right: QuarticPoint) -> Result<Line, Error> {
        if left == right || !self.contains_quartic(left) || !self.contains_quartic(right) {
            return Err(Error::InvalidPoint);
        }
        let coords = |point| match point {
            QuarticPoint::Infinity => (1, 0, 0),
            QuarticPoint::Affine { x, v } => (x, v, 1),
        };
        let (x, v, z) = coords(left);
        let (u, w, t) = coords(right);
        self.line(
            sub(v * t % self.p, z * w % self.p, self.p),
            sub(z * u % self.p, x * t % self.p, self.p),
            sub(x * w % self.p, v * u % self.p, self.p),
        )
    }

    fn on_line(&self, line: Line, point: QuarticPoint) -> bool {
        match point {
            QuarticPoint::Infinity => line.a == 0,
            QuarticPoint::Affine { x, v } => {
                (line.a * x + line.b * v + line.c).is_multiple_of(self.p)
            }
        }
    }

    fn section(&self, line: Line) -> Result<Section, Error> {
        if self.line(line.a, line.b, line.c)? != line {
            return Err(Error::InvalidLine);
        }
        if line.b != 0 {
            let inv = pow(line.b, self.p - 2, self.p);
            let m = sub(0, line.a * inv % self.p, self.p);
            let t = sub(0, line.c * inv % self.p, self.p);
            let mut poly = vec![
                sub(pow(t, 4, self.p), self.b, self.p),
                sub(4 * m * pow(t, 3, self.p) % self.p, self.a, self.p),
                6 * m * m * t * t % self.p,
                sub(4 * pow(m, 3, self.p) * t % self.p, 1, self.p),
                pow(m, 4, self.p),
            ];
            trim(&mut poly);
            let infinity = (5 - poly.len()) as u8;
            Ok(Section {
                poly,
                parameter_is_v: false,
                infinity,
            })
        } else if line.a != 0 {
            let x = sub(0, line.c * pow(line.a, self.p - 2, self.p) % self.p, self.p);
            Ok(Section {
                poly: vec![sub(0, self.rhs(x), self.p), 0, 0, 0, 1],
                parameter_is_v: true,
                infinity: 0,
            })
        } else {
            Ok(Section {
                poly: vec![1],
                parameter_is_v: false,
                infinity: 4,
            })
        }
    }

    fn section_point(&self, line: Line, parameter_is_v: bool, root: u64) -> QuarticPoint {
        if parameter_is_v {
            QuarticPoint::Affine {
                x: sub(0, line.c * pow(line.a, self.p - 2, self.p) % self.p, self.p),
                v: root,
            }
        } else {
            QuarticPoint::Affine {
                x: root,
                v: sub(0, (line.a * root + line.c) % self.p, self.p)
                    * pow(line.b, self.p - 2, self.p)
                    % self.p,
            }
        }
    }

    fn residual_roots(&self, poly: &[u64]) -> Result<Option<Vec<(u64, u8)>>, Error> {
        Ok(match poly.len() {
            1 if poly[0] != 0 => Some(vec![]),
            2 => Some(vec![(
                sub(0, poly[0], self.p) * pow(poly[1], self.p - 2, self.p) % self.p,
                1,
            )]),
            3 => {
                let disc = sub(
                    poly[1] * poly[1] % self.p,
                    4 * poly[2] * poly[0] % self.p,
                    self.p,
                );
                let roots = &self.square_roots[disc as usize];
                if roots.is_empty() {
                    None
                } else {
                    let inv = pow(2 * poly[2] % self.p, self.p - 2, self.p);
                    Some(
                        roots
                            .iter()
                            .map(|&s| {
                                (
                                    sub(s, poly[1], self.p) * inv % self.p,
                                    if disc == 0 { 2 } else { 1 },
                                )
                            })
                            .collect(),
                    )
                }
            }
            _ => return Err(Error::InvalidCertificate),
        })
    }

    /// Two known intersections leave a residual polynomial of degree at most two.
    /// `None` means that the residual does not split over the original field.
    pub fn line_relation(
        &self,
        left: QuarticPoint,
        right: QuarticPoint,
    ) -> Result<Option<RelationCertificate>, Error> {
        let line = self.secant(left, right)?;
        let section = self.section(line)?;
        let mut residual = section.poly.clone();
        let mut terms = BTreeMap::<QuarticPoint, u8>::new();
        for point in [left, right] {
            if let QuarticPoint::Affine { x, v } = point {
                residual = divide_root(
                    &residual,
                    if section.parameter_is_v { v } else { x },
                    self.p,
                )?;
                *terms.entry(point).or_default() += 1;
            }
        }
        let Some(roots) = self.residual_roots(&residual)? else {
            return Ok(None);
        };
        for (root, multiplicity) in roots {
            *terms
                .entry(self.section_point(line, section.parameter_is_v, root))
                .or_default() += multiplicity;
        }
        if section.infinity != 0 {
            terms.insert(QuarticPoint::Infinity, section.infinity);
        }
        let certificate = RelationCertificate {
            line,
            terms: terms.into_iter().collect(),
        };
        self.verify_relation(&certificate)?;
        Ok(Some(certificate))
    }

    /// Independent section reconstruction and elliptic norm replay.
    /// This verifier never calls the quadratic root solver or `line_relation`.
    pub fn verify_relation(&self, certificate: &RelationCertificate) -> Result<(), Error> {
        let section = self
            .section(certificate.line)
            .map_err(|_| Error::InvalidCertificate)?;
        let mut product = vec![1];
        let mut degree = 0u16;
        let mut infinity = 0;
        let mut seen = BTreeSet::new();
        let mut norm = EcPoint::Infinity;
        for &(point, multiplicity) in &certificate.terms {
            if multiplicity == 0
                || multiplicity > 4
                || !seen.insert(point)
                || !self.contains_quartic(point)
                || !self.on_line(certificate.line, point)
            {
                return Err(Error::InvalidCertificate);
            }
            degree += u16::from(multiplicity);
            match point {
                QuarticPoint::Infinity => infinity = multiplicity,
                QuarticPoint::Affine { x, v } => {
                    let root = if section.parameter_is_v { v } else { x };
                    for _ in 0..multiplicity {
                        let mut next = vec![0; product.len() + 1];
                        for (i, &coefficient) in product.iter().enumerate() {
                            next[i] = sub(next[i], root * coefficient % self.p, self.p);
                            next[i + 1] = (next[i + 1] + coefficient) % self.p;
                        }
                        product = next;
                    }
                }
            }
            let image = self.image(point)?;
            for _ in 0..multiplicity {
                norm = self.add_valid(norm, image);
            }
        }
        if degree != 4 || infinity != section.infinity || product.len() != section.poly.len() {
            return Err(Error::InvalidCertificate);
        }
        let leading = *section.poly.last().ok_or(Error::InvalidCertificate)?;
        for coefficient in &mut product {
            *coefficient = *coefficient * leading % self.p;
        }
        if product != section.poly || norm != EcPoint::Infinity {
            return Err(Error::InvalidCertificate);
        }
        Ok(())
    }
}

/// Collection and target budgets are enforced independently.
#[derive(Clone, Copy, Debug)]
pub struct Limits {
    pub pair_trials: usize,
    pub target_shifts: u64,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            pair_trials: MAX_PAIR_TRIALS,
            target_shifts: MAX_TARGET_SHIFTS,
        }
    }
}

impl Limits {
    fn validate(self) -> Result<(), Error> {
        if self.pair_trials > MAX_PAIR_TRIALS || self.target_shifts > MAX_TARGET_SHIFTS {
            Err(Error::InvalidBudget)
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct CollectionStats {
    pub rational_points: usize,
    pub possible_pairs: usize,
    pub pair_trials: usize,
    pub unique_lines: usize,
    pub duplicate_lines: usize,
    pub nonsplit_residuals: usize,
    pub certified_relations: usize,
    pub budget_exhausted: bool,
}

#[derive(Clone, Debug)]
pub struct Collection {
    pub certificates: Vec<RelationCertificate>,
    pub stats: CollectionStats,
}

/// Deterministic bounded collection, with misses and duplicates retained as counts.
pub fn collect_relations(cover: &Cover, limits: Limits) -> Result<Collection, Error> {
    limits.validate()?;
    let points = cover.rational_points();
    let possible_pairs = points.len() * (points.len() - 1) / 2;
    let mut stats = CollectionStats {
        rational_points: points.len(),
        possible_pairs,
        ..Default::default()
    };
    let mut seen = BTreeSet::new();
    let mut certificates = vec![];
    'pairs: for i in 0..points.len() {
        for j in i + 1..points.len() {
            if stats.pair_trials == limits.pair_trials {
                break 'pairs;
            }
            stats.pair_trials += 1;
            let line = cover.secant(points[i], points[j])?;
            if !seen.insert(line) {
                stats.duplicate_lines += 1;
                continue;
            }
            stats.unique_lines += 1;
            match cover.line_relation(points[i], points[j])? {
                Some(certificate) => certificates.push(certificate),
                None => stats.nonsplit_residuals += 1,
            }
        }
    }
    stats.certified_relations = certificates.len();
    stats.budget_exhausted = stats.pair_trials < possible_pairs;
    Ok(Collection {
        certificates,
        stats,
    })
}

struct RowReduction {
    modulus: u64,
    columns: usize,
    pivots: Vec<Option<Vec<u64>>>,
    rank: usize,
}

impl RowReduction {
    fn new(modulus: u64, columns: usize) -> Self {
        Self {
            modulus,
            columns,
            pivots: vec![None; columns],
            rank: 0,
        }
    }

    fn insert(&mut self, mut row: Vec<u64>) -> Result<bool, Error> {
        for column in 0..self.columns {
            let coefficient = row[column];
            if coefficient == 0 {
                continue;
            }
            if let Some(pivot) = &self.pivots[column] {
                for i in column..=self.columns {
                    row[i] = sub(row[i], coefficient * pivot[i] % self.modulus, self.modulus);
                }
            } else {
                let inv = pow(coefficient, self.modulus - 2, self.modulus);
                for value in &mut row {
                    *value = *value * inv % self.modulus;
                }
                for pivot in self.pivots.iter_mut().flatten() {
                    let coefficient = pivot[column];
                    for i in column..=self.columns {
                        pivot[i] = sub(pivot[i], coefficient * row[i] % self.modulus, self.modulus);
                    }
                }
                self.pivots[column] = Some(row);
                self.rank += 1;
                return Ok(true);
            }
        }
        if row[self.columns] != 0 {
            Err(Error::InconsistentRelations)
        } else {
            Ok(false)
        }
    }

    fn solution(&self) -> Option<Vec<u64>> {
        if self.rank != self.columns {
            return None;
        }
        self.pivots
            .iter()
            .map(|row| row.as_ref().map(|r| r[self.columns]))
            .collect()
    }
}

fn folded(cover: &Cover, point: EcPoint) -> Result<(EcPoint, i8), Error> {
    let negative = cover.neg(point)?;
    Ok(if point <= negative {
        (point, 1)
    } else {
        (negative, -1)
    })
}

/// Preparation retains exact certificates and distinguishes norm images from columns.
#[derive(Clone, Debug)]
pub struct Precomputation {
    cover: Cover,
    generator: EcPoint,
    order: u64,
    base: Vec<EcPoint>,
    logs: Option<Vec<u64>>,
    pub collection: Collection,
    pub usable_norm_images: usize,
    pub matrix_columns: usize,
    pub matrix_rank: usize,
    pub independent_line_rows: usize,
    pub dependent_line_rows: usize,
    pub zero_projected_rows: usize,
    pub anchor_multiple: u64,
    pub replayed_factor_logs: usize,
}

impl Precomputation {
    pub fn is_complete(&self) -> bool {
        self.logs.is_some()
    }

    pub fn subgroup_order(&self) -> u64 {
        self.order
    }

    pub fn factor_base(&self) -> &[EcPoint] {
        &self.base
    }

    pub fn factor_logs(&self) -> Option<&[u64]> {
        self.logs.as_deref()
    }

    pub fn cover(&self) -> &Cover {
        &self.cover
    }

    pub fn generator(&self) -> EcPoint {
        self.generator
    }
}

/// Prepare projected factor-base logs using certified line rows and one known anchor.
/// Requires a prime-order elliptic group; no unsupported cofactor is guessed.
pub fn prepare(cover: Cover, generator: EcPoint, limits: Limits) -> Result<Precomputation, Error> {
    limits.validate()?;
    if generator == EcPoint::Infinity || !cover.contains_ec(generator) {
        return Err(Error::InvalidGenerator);
    }
    let order = cover.group_order();
    if order <= 2 || !is_prime(order) {
        return Err(Error::NonPrimeGroupOrder);
    }
    let points = cover.rational_points();
    let images: BTreeSet<_> = points
        .iter()
        .filter_map(|&point| {
            let image = cover.image(point).ok()?;
            (image != EcPoint::Infinity).then_some(image)
        })
        .collect();
    let mut base_set = BTreeSet::new();
    for &point in &images {
        base_set.insert(folded(&cover, point)?.0);
    }
    let base: Vec<_> = base_set.into_iter().collect();
    let columns = base.len();
    let index: BTreeMap<_, _> = base
        .iter()
        .enumerate()
        .map(|(i, &point)| (point, i))
        .collect();
    let mut matrix = RowReduction::new(order, columns);
    let mut anchor_multiple = 0;
    let mut anchor = EcPoint::Infinity;
    // These are KNOWN generator multiples, not unknown factor-base logarithms.
    for scalar in 1..order {
        anchor = cover.add_valid(anchor, generator);
        let (point, sign) = folded(&cover, anchor)?;
        if let Some(&column) = index.get(&point) {
            let mut row = vec![0; columns + 1];
            row[column] = 1;
            row[columns] = if sign == 1 {
                scalar
            } else {
                sub(0, scalar, order)
            };
            matrix.insert(row)?;
            anchor_multiple = scalar;
            break;
        }
    }
    let collection = collect_relations(&cover, limits)?;
    let mut independent_line_rows = 0;
    let mut dependent_line_rows = 0;
    let mut zero_projected_rows = 0;
    for certificate in &collection.certificates {
        let mut row = vec![0; columns + 1];
        for &(point, multiplicity) in &certificate.terms {
            let image = cover.image(point)?;
            if image == EcPoint::Infinity {
                continue;
            }
            let (representative, sign) = folded(&cover, image)?;
            let column = index[&representative];
            row[column] = if sign == 1 {
                (row[column] + u64::from(multiplicity)) % order
            } else {
                sub(row[column], u64::from(multiplicity), order)
            };
        }
        if row.iter().all(|&x| x == 0) {
            zero_projected_rows += 1;
            continue;
        }
        if matrix.insert(row)? {
            independent_line_rows += 1;
        } else {
            dependent_line_rows += 1;
        }
    }
    let logs = if columns != 0 && anchor_multiple != 0 {
        matrix.solution()
    } else {
        None
    };
    let mut replayed_factor_logs = 0;
    if let Some(logs) = &logs {
        for (&point, &log) in base.iter().zip(logs) {
            if cover.mul(generator, log)? != point {
                return Err(Error::InvalidFactorBaseLog);
            }
            replayed_factor_logs += 1;
        }
    }
    Ok(Precomputation {
        cover,
        generator,
        order,
        base,
        logs,
        usable_norm_images: images.len(),
        matrix_columns: columns,
        matrix_rank: matrix.rank,
        collection,
        independent_line_rows,
        dependent_line_rows,
        zero_projected_rows,
        anchor_multiple,
        replayed_factor_logs,
    })
}

/// A failed target or insufficient-rank run remains an explicit report.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RecoveryReport {
    pub status: &'static str,
    pub target: EcPoint,
    pub scalar: Option<u64>,
    pub verified: bool,
    pub shifts_tested: u64,
    pub shift: Option<u64>,
    /// `pi(fiber)=fiber_sign*(target+shift*generator)`.
    pub fiber_sign: Option<i8>,
    pub fiber: Option<(QuarticPoint, QuarticPoint)>,
}

/// Bounded individual logarithm using a signed rational target fiber.
/// The target scalar is not an input, and failed preparation is never bypassed.
pub fn recover(
    precomputed: &Precomputation,
    target: EcPoint,
    limits: Limits,
) -> Result<RecoveryReport, Error> {
    limits.validate()?;
    let cover = &precomputed.cover;
    if !cover.contains_ec(target) {
        return Err(Error::InvalidPoint);
    }
    let mut report = RecoveryReport {
        status: "rank_deficient",
        target,
        scalar: None,
        verified: false,
        shifts_tested: 0,
        shift: None,
        fiber_sign: None,
        fiber: None,
    };
    let Some(logs) = &precomputed.logs else {
        return Ok(report);
    };
    if precomputed.collection.stats.budget_exhausted {
        report.status = "pair_budget_exhausted";
        return Ok(report);
    }
    report.status = "target_budget_exhausted";
    let mut shifted = target;
    for shift in 0..limits.target_shifts.min(precomputed.order) {
        report.shifts_tested += 1;
        let (representative, sign) = folded(cover, shifted)?;
        let candidate = if shifted == EcPoint::Infinity {
            Some(sub(0, shift, precomputed.order))
        } else if let Ok(column) = precomputed.base.binary_search(&representative) {
            let log = if sign == 1 {
                logs[column]
            } else {
                sub(0, logs[column], precomputed.order)
            };
            Some(sub(log, shift, precomputed.order))
        } else {
            None
        };
        if let Some(scalar) = candidate {
            if cover.mul(precomputed.generator, scalar)? != target {
                return Err(Error::InvalidFactorBaseLog);
            }
            if shifted != EcPoint::Infinity {
                let negative = cover.neg(shifted)?;
                for point in cover.rational_points() {
                    let image = cover.image(point)?;
                    if image == shifted || image == negative {
                        if let QuarticPoint::Affine { x, v } = point {
                            report.fiber = Some((
                                point,
                                QuarticPoint::Affine {
                                    x,
                                    v: sub(0, v, cover.p),
                                },
                            ));
                            report.fiber_sign = Some(if image == shifted { 1 } else { -1 });
                            break;
                        }
                    }
                }
                if report.fiber.is_none() {
                    return Err(Error::InvalidFactorBaseLog);
                }
            }
            report.status = "complete";
            report.scalar = Some(scalar);
            report.verified = true;
            report.shift = Some(shift);
            return Ok(report);
        }
        shifted = cover.add_valid(shifted, precomputed.generator);
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> Cover {
        Cover::new(53, 2, 1).unwrap()
    }

    fn generator() -> EcPoint {
        EcPoint::Affine { x: 0, y: 1 }
    }

    #[test]
    fn rejects_unsupported_and_noncanonical_inputs() {
        for p in [0, 2, 3, 4, 9, 263, u64::MAX] {
            assert_eq!(Cover::new(p, 0, 1).unwrap_err(), Error::UnsupportedField);
        }
        assert_eq!(
            Cover::new(53, 53, 1).unwrap_err(),
            Error::NoncanonicalCoefficient
        );
        assert_eq!(Cover::new(53, 0, 0).unwrap_err(), Error::SingularCurve);
        let cover = fixture();
        assert_eq!(
            cover.image(QuarticPoint::Affine { x: 53, v: 1 }),
            Err(Error::InvalidPoint)
        );
        assert_eq!(
            prepare(cover.clone(), EcPoint::Infinity, Limits::default()).unwrap_err(),
            Error::InvalidGenerator
        );
        assert_eq!(
            cover.mul(EcPoint::Affine { x: 0, y: 0 }, 0),
            Err(Error::InvalidPoint)
        );
        assert_eq!(
            collect_relations(
                &cover,
                Limits {
                    pair_trials: MAX_PAIR_TRIALS + 1,
                    target_shifts: 1
                }
            )
            .unwrap_err(),
            Error::InvalidBudget
        );
    }

    #[test]
    fn checked_four_point_section_matches_example() {
        let cover = fixture();
        let certificate = cover
            .line_relation(
                QuarticPoint::Affine { x: 0, v: 52 },
                QuarticPoint::Affine { x: 29, v: 28 },
            )
            .unwrap()
            .unwrap();
        let points = [(0, 52), (29, 28), (36, 35), (46, 45)];
        assert_eq!(
            certificate.terms,
            points
                .map(|(x, v)| (QuarticPoint::Affine { x, v }, 1))
                .to_vec()
        );
        let mut sum = EcPoint::Infinity;
        for (x, v) in points {
            sum = cover
                .add(sum, cover.image(QuarticPoint::Affine { x, v }).unwrap())
                .unwrap();
        }
        assert_eq!(sum, EcPoint::Infinity);
        assert_eq!(cover.group_order(), 59);
        assert_eq!(cover.rational_points().len(), 45);
    }

    #[test]
    fn section_tampering_is_rejected_even_with_zero_norm() {
        let cover = fixture();
        let certificate = cover
            .line_relation(
                QuarticPoint::Affine { x: 0, v: 52 },
                QuarticPoint::Affine { x: 29, v: 28 },
            )
            .unwrap()
            .unwrap();
        let mut changed = certificate.clone();
        changed.terms[0].1 = 2;
        assert_eq!(
            cover.verify_relation(&changed),
            Err(Error::InvalidCertificate)
        );
        changed = certificate.clone();
        changed.line.c = (changed.line.c + 1) % 53;
        assert_eq!(
            cover.verify_relation(&changed),
            Err(Error::InvalidCertificate)
        );
        // Opposite elliptic images sum to zero, but are not this line's section.
        changed.terms = vec![
            (QuarticPoint::Affine { x: 0, v: 1 }, 2),
            (QuarticPoint::Affine { x: 0, v: 23 }, 2),
        ];
        assert_eq!(
            cover.verify_relation(&changed),
            Err(Error::InvalidCertificate)
        );
        changed = certificate;
        changed.terms[1] = changed.terms[0];
        assert_eq!(
            cover.verify_relation(&changed),
            Err(Error::InvalidCertificate)
        );
    }

    #[test]
    fn infinity_and_repeated_intersections_are_counted() {
        let cover = Cover::new(7, 0, 1).unwrap();
        let certificate = cover
            .line_relation(QuarticPoint::Infinity, QuarticPoint::Affine { x: 0, v: 1 })
            .unwrap()
            .unwrap();
        assert_eq!(
            certificate.terms,
            vec![
                (QuarticPoint::Infinity, 1),
                (QuarticPoint::Affine { x: 0, v: 1 }, 3)
            ]
        );
        cover.verify_relation(&certificate).unwrap();
        let infinity = RelationCertificate {
            line: cover.line(0, 0, 1).unwrap(),
            terms: vec![(QuarticPoint::Infinity, 4)],
        };
        cover.verify_relation(&infinity).unwrap();
        assert_eq!(
            prepare(cover, EcPoint::Affine { x: 0, y: 1 }, Limits::default()).unwrap_err(),
            Error::NonPrimeGroupOrder
        );
    }

    #[test]
    fn all_pair_sections_match_independent_rational_point_control() {
        let cover = fixture();
        let points = cover.rational_points();
        let mut unsplit = 0;
        for i in 0..points.len() {
            for j in i + 1..points.len() {
                let line = cover.secant(points[i], points[j]).unwrap();
                let visible: BTreeSet<_> = points
                    .iter()
                    .copied()
                    .filter(|&point| cover.on_line(line, point))
                    .collect();
                if let Some(certificate) = cover.line_relation(points[i], points[j]).unwrap() {
                    cover.verify_relation(&certificate).unwrap();
                    assert_eq!(
                        visible,
                        certificate.terms.iter().map(|&(point, _)| point).collect()
                    );
                } else {
                    unsplit += 1;
                    assert!(visible.len() <= 3);
                }
            }
        }
        assert!(unsplit > 0);
    }

    #[test]
    fn complete_known_answer_controls_use_no_target_scalar_input() {
        let cover = fixture();
        let precomputed = prepare(cover.clone(), generator(), Limits::default()).unwrap();
        assert!(
            precomputed.is_complete(),
            "rank={} columns={}",
            precomputed.matrix_rank,
            precomputed.matrix_columns
        );
        assert!(precomputed.independent_line_rows > 0);
        assert_eq!(precomputed.replayed_factor_logs, precomputed.matrix_columns);
        for secret in 0..59 {
            let target = cover.mul(generator(), secret).unwrap();
            let report = recover(&precomputed, target, Limits::default()).unwrap();
            assert_eq!(report.status, "complete");
            assert_eq!(report.scalar, Some(secret));
            assert!(report.verified);
            if let Some((left, right)) = report.fiber {
                let shifted = cover
                    .add(
                        target,
                        cover.mul(generator(), report.shift.unwrap()).unwrap(),
                    )
                    .unwrap();
                let expected = if report.fiber_sign == Some(1) {
                    shifted
                } else {
                    cover.neg(shifted).unwrap()
                };
                assert_eq!(cover.image(left).unwrap(), expected);
                assert_eq!(cover.image(right).unwrap(), expected);
            }
        }
    }

    #[test]
    fn budgets_and_rank_deficiency_remain_failures() {
        let cover = fixture();
        let limits = Limits {
            pair_trials: 0,
            target_shifts: 10,
        };
        let precomputed = prepare(cover.clone(), generator(), limits).unwrap();
        assert!(!precomputed.is_complete());
        assert!(precomputed.collection.stats.budget_exhausted);
        let report = recover(&precomputed, generator(), limits).unwrap();
        assert_eq!(report.status, "rank_deficient");
        assert_eq!(report.scalar, None);
        let pair_limits = Limits {
            pair_trials: 989,
            target_shifts: 10,
        };
        let partial = prepare(cover.clone(), generator(), pair_limits).unwrap();
        assert!(partial.is_complete());
        assert!(partial.collection.stats.budget_exhausted);
        let report = recover(&partial, generator(), Limits::default()).unwrap();
        assert_eq!(report.status, "pair_budget_exhausted");
        assert_eq!(report.scalar, None);
        assert_eq!(report.shifts_tested, 0);
        let precomputed = prepare(cover, generator(), Limits::default()).unwrap();
        let report = recover(
            &precomputed,
            generator(),
            Limits {
                pair_trials: 1,
                target_shifts: 0,
            },
        )
        .unwrap();
        assert_eq!(report.status, "target_budget_exhausted");
        assert!(!report.verified);
    }

    #[test]
    fn row_reduction_uses_group_order_not_field_characteristic() {
        let mut matrix = RowReduction::new(59, 2);
        matrix.insert(vec![1, 2, 3]).unwrap();
        matrix.insert(vec![0, 1, 58]).unwrap();
        assert_eq!(matrix.solution(), Some(vec![5, 58]));
        assert_eq!(
            matrix.insert(vec![0, 0, 1]),
            Err(Error::InconsistentRelations)
        );
    }
}
