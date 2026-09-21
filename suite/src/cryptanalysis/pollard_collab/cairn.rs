//! cairn transport — publish distinguished points as paid claims on a
//! [cairn](https://github.com/aburan28/cairn) *piecework* objective, and
//! read the objective's log back as the shared DP table.
//!
//! The mailbox and TCP transports move check-ins between peers who trust
//! each other to the extent of verifying every record.  This transport
//! moves the same records through a network that *pays* for them: a
//! coordinator posts an objective whose checker verifies one
//! distinguished point `(x, y, a, b)` with `a·P + b·Q = (x, y)`, and
//! every novel accepted point is paid `unit_price` from the pool.  The
//! log of accepted claims is the DP table, so a collision between any
//! two contributors' points is visible to every node that reads it.
//!
//! ## What travels
//!
//! A point goes out as cairn's commit–reveal pair:
//!
//! ```text
//! POST /submit?kind=commitment  {type, objective_id, submitter, hash, created_at}
//!     … next epoch …
//! POST /submit?kind=claim       {type, objective_id, submitter, artifact, nonce, created_at, cites: []}
//! ```
//!
//! where `hash = sha256(digest({objective_id, artifact}) | submitter | nonce)`
//! and `digest` is `"sha256:" + hex(sha256(canonical JSON))`.  The reveal
//! must land in a strictly later epoch than the commitment, so a
//! commitment is remembered (and persisted, see [`CairnConfig::state_path`])
//! until the epoch turns.  Both encodings are consensus-critical on the
//! cairn side and are pinned here against its frozen conformance vectors.
//!
//! The artifact is exactly `{"x","y","a","b"}` in minimal lowercase hex
//! with `2y ≤ p`: the shape the rho checkers accept, and the reason a
//! point has one spelling whichever walk reached it.  A negated record is
//! folded to the canonical one before it leaves, coefficients included.
//!
//! ## What comes back
//!
//! `GET /log` is the whole ledger, one JSON entry per line.  Every claim
//! on the objective becomes a check-in from the synthetic peer
//! `cairn:<submitter>` and is merged with full verification, so the
//! local [`SharedState`] holds every point the network has accepted and
//! [`solve_collision`](super::state::solve_collision) fires the moment
//! one of ours meets one of theirs.  Under a walk without the negation
//! map the negated twin is merged too, because canonicalisation folded
//! it away and the collision `(x, y)` against `(x, −y)` still solves.
//!
//! When the state solves and an *answer objective* is configured, the
//! discrete log is committed to it as `{"k": <64 hex>}` — the artifact
//! the ladder's answer checkers accept — and revealed next epoch like any
//! other claim.
//!
//! ## Identity
//!
//! A nickname submitter needs no signature.  A key-shaped submitter (an
//! Ed25519 public key, 64 hex) must sign every record over the canonical
//! bytes of the record without its signature; [`Submitter::from_identity_file`]
//! reads the `{"public", "secret"}` file `cairn identity` writes and
//! signs with this crate's own Ed25519.

use std::collections::{BTreeMap, HashSet};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::time::Duration;

use num_bigint::BigUint;
use num_traits::Zero;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value as Json};

use super::job::{hex_of, parse_hex, JobContext, PROTOCOL_VERSION};
use super::state::{now_secs, CheckIn, SharedState};
use super::walk::DpRecord;
use crate::ecc::ed25519::{ed25519_pubkey, ed25519_sign};
use crate::hash::sha256::sha256;

// ── canonical encoding and content addressing ───────────────────────────────

/// cairn's canonical JSON: keys sorted by code point, no whitespace,
/// raw UTF-8, only `"`, `\` and controls below 0x20 escaped (the five
/// short forms where they exist), integers only.  Pinned against
/// cairn's `conformance/vectors.json` in the tests below.
pub fn canonical(value: &Json) -> Result<String, String> {
    let mut out = String::new();
    write_canonical(value, &mut out)?;
    Ok(out)
}

fn write_canonical(value: &Json, out: &mut String) -> Result<(), String> {
    match value {
        Json::Null => out.push_str("null"),
        Json::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Json::Number(n) => {
            if let Some(i) = n.as_i64() {
                out.push_str(&i.to_string());
            } else if let Some(u) = n.as_u64() {
                out.push_str(&u.to_string());
            } else {
                return Err(format!(
                    "{n} is not an integer; cairn records carry no floats"
                ));
            }
        }
        Json::String(s) => write_escaped(s, out),
        Json::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_canonical(item, out)?;
            }
            out.push(']');
        }
        Json::Object(map) => {
            // Sort explicitly rather than trusting the map's order: UTF-8
            // byte order equals code-point order, which is what cairn sorts by.
            let sorted: BTreeMap<&String, &Json> = map.iter().collect();
            out.push('{');
            for (i, (key, item)) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_escaped(key, out);
                out.push(':');
                write_canonical(item, out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

fn write_escaped(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\u{c}' => out.push_str("\\f"),
            '\r' => out.push_str("\\r"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `"sha256:" + hex(sha256(canonical(value)))` — a cairn content address.
pub fn digest(value: &Json) -> Result<String, String> {
    Ok(format!(
        "sha256:{}",
        hex::encode(sha256(canonical(value)?.as_bytes()))
    ))
}

/// The hash a commitment carries, exactly as `cairn::records::commitment_hash`
/// computes it: `sha256(digest({objective_id, artifact}) | submitter | nonce)`.
pub fn commitment_hash(
    objective_id: &str,
    submitter: &str,
    artifact: &Json,
    nonce: &str,
) -> Result<String, String> {
    if submitter.contains('|') {
        return Err("a submitter may not contain `|`".into());
    }
    let inner = digest(&json!({ "objective_id": objective_id, "artifact": artifact }))?;
    let mut buf = Vec::with_capacity(inner.len() + submitter.len() + nonce.len() + 2);
    buf.extend_from_slice(inner.as_bytes());
    buf.push(b'|');
    buf.extend_from_slice(submitter.as_bytes());
    buf.push(b'|');
    buf.extend_from_slice(nonce.as_bytes());
    Ok(format!("sha256:{}", hex::encode(sha256(&buf))))
}

/// `YYYY-MM-DDTHH:MM:SS+00:00`, the timestamp shape every cairn record
/// carries.  The epoch a record belongs to is derived from this field
/// and never from a clock, so the client writes it and the node reads it.
pub fn format_utc(unix_seconds: u64) -> String {
    let days = (unix_seconds / 86_400) as i64;
    let rem = unix_seconds % 86_400;
    // Howard Hinnant's civil-from-days.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}+00:00",
        rem / 3600,
        (rem / 60) % 60,
        rem % 60
    )
}

/// cairn's epoch of an instant: `seconds / epoch_seconds`.
pub fn epoch_of(unix_seconds: u64, epoch_seconds: u64) -> u64 {
    unix_seconds.checked_div(epoch_seconds).unwrap_or(0)
}

// ── artifacts ───────────────────────────────────────────────────────────────

/// The `{x, y, a, b}` artifact for a record, folded to the representative
/// with `2y ≤ p` (coefficients negated to match) so that one point has one
/// spelling whichever walk reached it.
pub fn canonical_artifact(ctx: &JobContext, rec: &DpRecord) -> Result<Json, String> {
    let x = parse_hex(&rec.x)?;
    let mut y = parse_hex(&rec.y)?;
    let (mut a, mut b) = rec.coefficients()?;
    if &y << 1 > ctx.p {
        y = &ctx.p - y;
        a = neg_mod(&a, &ctx.n);
        b = neg_mod(&b, &ctx.n);
    }
    Ok(json!({
        "x": hex_of(&x),
        "y": hex_of(&y),
        "a": hex_of(&a),
        "b": hex_of(&b),
    }))
}

/// A record from a log artifact, if it has the four hex fields.  The
/// walker index and step count are not in the artifact (they would let
/// a copier re-mint a point by relabelling it), so they read as zero.
pub fn record_from_artifact(artifact: &Json) -> Option<DpRecord> {
    let field = |k: &str| artifact.get(k)?.as_str().map(String::from);
    Some(DpRecord {
        walker: 0,
        steps: 0,
        x: field("x")?,
        y: field("y")?,
        a: field("a")?,
        b: field("b")?,
    })
}

/// The negated twin `(x, −y, −a, −b)`, also a valid record.  Under a walk
/// without the negation map the DP table keys on `x:y`, so a canonical
/// point from the log and a local `(x, −y)` would never meet; merging the
/// twin as well lets that collision solve.
fn negated(ctx: &JobContext, rec: &DpRecord) -> Result<DpRecord, String> {
    let y = parse_hex(&rec.y)?;
    let (a, b) = rec.coefficients()?;
    Ok(DpRecord {
        walker: rec.walker,
        steps: rec.steps,
        x: rec.x.clone(),
        y: hex_of(&(if y.is_zero() { y } else { &ctx.p - y })),
        a: hex_of(&neg_mod(&a, &ctx.n)),
        b: hex_of(&neg_mod(&b, &ctx.n)),
    })
}

fn neg_mod(v: &BigUint, n: &BigUint) -> BigUint {
    if v.is_zero() {
        BigUint::zero()
    } else {
        n - v
    }
}

// ── identity ────────────────────────────────────────────────────────────────

/// Who signs.  A nickname is Stage-0 cairn: anyone may submit as anyone
/// and nothing is checked.  A key is an Ed25519 public key, and cairn
/// refuses any record under it that does not carry a valid signature.
#[derive(Clone)]
pub enum Submitter {
    Nickname(String),
    Key { seed: [u8; 32], public_hex: String },
}

impl Submitter {
    /// Read the `{"public": <64 hex>, "secret": <64 hex>}` file that
    /// `cairn identity --out FILE` writes.
    pub fn from_identity_file(path: &Path) -> Result<Self, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let v: Json =
            serde_json::from_str(&text).map_err(|e| format!("{}: {e}", path.display()))?;
        let secret_hex = v
            .get("secret")
            .and_then(Json::as_str)
            .ok_or_else(|| format!("{}: no `secret` field", path.display()))?;
        let bytes =
            hex::decode(secret_hex).map_err(|e| format!("{}: secret: {e}", path.display()))?;
        let seed: [u8; 32] = bytes
            .try_into()
            .map_err(|_| format!("{}: secret must be 32 bytes", path.display()))?;
        let public_hex = hex::encode(ed25519_pubkey(&seed));
        if let Some(declared) = v.get("public").and_then(Json::as_str) {
            if declared != public_hex {
                return Err(format!(
                    "{}: the public key does not match the secret",
                    path.display()
                ));
            }
        }
        Ok(Self::Key { seed, public_hex })
    }

    /// The `submitter` field.
    pub fn name(&self) -> &str {
        match self {
            Self::Nickname(n) => n,
            Self::Key { public_hex, .. } => public_hex,
        }
    }

    /// Hex signature over the canonical bytes of `payload`, for a key.
    fn sign(&self, payload: &Json) -> Result<Option<String>, String> {
        match self {
            Self::Nickname(_) => Ok(None),
            Self::Key { seed, .. } => Ok(Some(hex::encode(ed25519_sign(
                canonical(payload)?.as_bytes(),
                seed,
            )))),
        }
    }
}

// ── configuration and persisted state ───────────────────────────────────────

#[derive(Clone)]
pub struct CairnConfig {
    /// `http://host:port` of a `cairn serve --queue …` node.
    pub url: String,
    /// The piecework objective the points are claims on.
    pub objective_id: String,
    pub submitter: Submitter,
    /// Where to claim `k` once the search solves, if anywhere.
    pub answer_objective: Option<String>,
    /// The node's epoch length (`CAIRN_EPOCH_SECONDS`, 600 by default).
    /// A reveal is refused unless it lands in a strictly later epoch than
    /// its commitment, so the client has to know the length.
    pub epoch_secs: u64,
    /// Pending commitments outlive the process here, so a restart still
    /// reveals what it committed.  `None` keeps them in memory only.
    pub state_path: Option<PathBuf>,
    /// Where `created_at` comes from.  The wall clock unless a test says
    /// otherwise: epochs are derived from the timestamps records carry,
    /// so a test can turn the epoch by moving this rather than sleeping.
    pub clock: Clock,
}

/// A source of Unix seconds.
pub type Clock = std::sync::Arc<dyn Fn() -> u64 + Send + Sync>;

/// The wall clock.
pub fn wall_clock() -> Clock {
    std::sync::Arc::new(now_secs)
}

/// A commitment waiting for the epoch to turn.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
struct Pending {
    objective_id: String,
    artifact: Json,
    nonce: String,
    commit_epoch: u64,
    /// What this claim answers: a DP key, or `answer` for `k`.
    key: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct Persisted {
    pending: Vec<Pending>,
    /// Keys already committed (pending or revealed), so a DP is never
    /// submitted twice from here.
    submitted: Vec<String>,
    /// Ids of the claims we revealed, for matching verdicts and settlements.
    revealed: Vec<String>,
    /// Highest log sequence merged so far.
    last_seq: u64,
}

/// Counters for status lines.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct CairnStats {
    pub committed: u64,
    pub revealed: u64,
    pub refused: u64,
    /// Our claims the log has paid, and how much.
    pub paid_units: u64,
    pub paid_total: u64,
    pub rejected: u64,
    /// Points read from the log (every submitter), and those that failed
    /// verification here.
    pub log_dps: u64,
    pub log_rejected: u64,
}

/// One node's view of the objective, plus its outbox.
pub struct CairnTransport {
    cfg: CairnConfig,
    st: Persisted,
    submitted: HashSet<String>,
    revealed: HashSet<String>,
    /// DP keys the log already holds an accepted claim for.
    log_keys: HashSet<String>,
    stats: CairnStats,
}

/// What one publish did.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct PublishReport {
    pub committed: usize,
    pub skipped: usize,
}

/// What one sync did.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SyncReport {
    pub entries: usize,
    pub accepted_dps: usize,
    pub rejected_dps: usize,
    pub revealed: usize,
    pub refused: usize,
    pub solved_now: bool,
}

impl CairnTransport {
    pub fn open(cfg: CairnConfig) -> Result<Self, String> {
        if cfg.epoch_secs == 0 {
            return Err("epoch_secs must be ≥ 1".into());
        }
        let st = match &cfg.state_path {
            Some(p) if p.exists() => {
                let text =
                    std::fs::read_to_string(p).map_err(|e| format!("{}: {e}", p.display()))?;
                serde_json::from_str(&text).map_err(|e| format!("{}: {e}", p.display()))?
            }
            _ => Persisted::default(),
        };
        let submitted = st.submitted.iter().cloned().collect();
        let revealed = st.revealed.iter().cloned().collect();
        Ok(Self {
            cfg,
            st,
            submitted,
            revealed,
            log_keys: HashSet::new(),
            stats: CairnStats::default(),
        })
    }

    pub fn stats(&self) -> &CairnStats {
        &self.stats
    }

    pub fn pending(&self) -> usize {
        self.st.pending.len()
    }

    pub fn submitter(&self) -> &str {
        self.cfg.submitter.name()
    }

    fn save(&self) -> Result<(), String> {
        let Some(p) = &self.cfg.state_path else {
            return Ok(());
        };
        let text = serde_json::to_string_pretty(&self.st).map_err(|e| e.to_string())?;
        let tmp = p.with_extension("tmp");
        std::fs::write(&tmp, text).map_err(|e| format!("{}: {e}", tmp.display()))?;
        std::fs::rename(&tmp, p).map_err(|e| format!("{}: {e}", p.display()))
    }

    /// Commit every new distinguished point in a check-in (and the
    /// solution, when an answer objective is configured).
    pub fn publish(&mut self, ctx: &JobContext, ci: &CheckIn) -> Result<PublishReport, String> {
        let mut rep = PublishReport::default();
        for rec in &ci.dps {
            let artifact = canonical_artifact(ctx, rec)?;
            let key = artifact_key(&artifact);
            if self.submitted.contains(&key) || self.log_keys.contains(&key) {
                rep.skipped += 1;
                continue;
            }
            self.commit(&self.cfg.objective_id.clone(), artifact, key)?;
            rep.committed += 1;
        }
        if let (Some(answer), Some(x)) = (&self.cfg.answer_objective, &ci.solution) {
            if !self.submitted.contains("answer") {
                let k = parse_hex(x)?;
                let artifact = json!({ "k": format!("{:064x}", k) });
                self.commit(&answer.clone(), artifact, "answer".to_string())?;
                rep.committed += 1;
            }
        }
        Ok(rep)
    }

    /// Commit `k` for the answer objective, if the state holds a solution
    /// and it has not been committed yet.  Called from `sync` too, so a
    /// solution reached by merging the *log* is claimed as well.
    fn commit_answer(&mut self, state: &SharedState) -> Result<bool, String> {
        let (Some(answer), Some(x)) = (&self.cfg.answer_objective, &state.solution) else {
            return Ok(false);
        };
        if self.submitted.contains("answer") {
            return Ok(false);
        }
        let artifact = json!({ "k": format!("{:064x}", x) });
        self.commit(&answer.clone(), artifact, "answer".to_string())?;
        Ok(true)
    }

    fn commit(&mut self, objective_id: &str, artifact: Json, key: String) -> Result<(), String> {
        let mut nonce_bytes = [0u8; 16];
        crate::utils::random_bytes(&mut nonce_bytes);
        let nonce = hex::encode(nonce_bytes);
        let submitter = self.cfg.submitter.name().to_string();
        let hash = commitment_hash(objective_id, &submitter, &artifact, &nonce)?;
        let now = (self.cfg.clock)();
        let mut record = json!({
            "type": "commitment",
            "objective_id": objective_id,
            "submitter": submitter,
            "hash": hash,
            "created_at": format_utc(now),
        });
        if let Some(sig) = self.cfg.submitter.sign(&record)? {
            record["signature"] = Json::String(sig);
        }
        let (status, body) = self.post("/submit?kind=commitment", &record)?;
        if status != 202 {
            return Err(format!("commitment refused ({status}): {body}"));
        }
        self.st.pending.push(Pending {
            objective_id: objective_id.to_string(),
            artifact,
            nonce,
            commit_epoch: epoch_of(now, self.cfg.epoch_secs),
            key: key.clone(),
        });
        self.st.submitted.push(key.clone());
        self.submitted.insert(key);
        self.stats.committed += 1;
        self.save()
    }

    /// Reveal every commitment whose epoch has closed.  Returns
    /// `(revealed, refused)`.
    fn reveal_due(&mut self) -> Result<(usize, usize), String> {
        let now = (self.cfg.clock)();
        let epoch = epoch_of(now, self.cfg.epoch_secs);
        let due: Vec<Pending> = self
            .st
            .pending
            .iter()
            .filter(|p| p.commit_epoch < epoch)
            .cloned()
            .collect();
        let (mut revealed, mut refused) = (0, 0);
        for p in due {
            let submitter = self.cfg.submitter.name().to_string();
            let mut record = json!({
                "type": "claim",
                "objective_id": p.objective_id,
                "submitter": submitter,
                "artifact": p.artifact,
                "nonce": p.nonce,
                "created_at": format_utc(now),
                "cites": [],
            });
            if let Some(sig) = self.cfg.submitter.sign(&record)? {
                record["signature"] = Json::String(sig);
            }
            match self.post("/submit?kind=claim", &record) {
                Ok((202, _)) => {
                    // The claim's id is the digest of the record as sent,
                    // `type` and signature included -- what the log's
                    // settlement and verdict entries name.
                    let id = digest(&record)?;
                    self.st.revealed.push(id.clone());
                    self.revealed.insert(id);
                    self.st.pending.retain(|q| q != &p);
                    self.stats.revealed += 1;
                    revealed += 1;
                }
                Ok((status, body)) if (400..500).contains(&status) => {
                    // Refused at the boundary: malformed or stale. Retrying
                    // cannot help, so drop it and let the point be walked
                    // again by whoever holds the unit.
                    eprintln!("[cairn] reveal refused ({status}): {body}");
                    self.st.pending.retain(|q| q != &p);
                    self.stats.refused += 1;
                    refused += 1;
                }
                Ok((status, body)) => {
                    eprintln!("[cairn] reveal not accepted ({status}), will retry: {body}");
                }
                Err(e) => {
                    eprintln!("[cairn] reveal failed, will retry: {e}");
                }
            }
        }
        if revealed + refused > 0 {
            self.save()?;
        }
        Ok((revealed, refused))
    }

    /// Read the log, merge every accepted point on the objective into
    /// `state`, note what the network paid us, reveal what is due, and
    /// claim the answer if the merge solved the instance.
    pub fn sync(
        &mut self,
        ctx: &JobContext,
        state: &mut SharedState,
    ) -> Result<SyncReport, String> {
        let mut rep = SyncReport::default();
        let (status, body) = self.get("/log")?;
        if status != 200 {
            return Err(format!("GET /log -> {status}: {body}"));
        }
        let me = self.cfg.submitter.name().to_string();
        let mut max_seq = self.st.last_seq;
        for line in body.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            let entry: Json = match serde_json::from_str(line) {
                Ok(v) => v,
                Err(_) => continue,
            };
            let seq = entry.get("seq").and_then(Json::as_u64).unwrap_or(0);
            if seq <= self.st.last_seq {
                continue;
            }
            max_seq = max_seq.max(seq);
            rep.entries += 1;
            let kind = entry.get("kind").and_then(Json::as_str).unwrap_or("");
            let Some(payload) = entry.get("payload") else {
                continue;
            };
            let objective = payload
                .get("objective_id")
                .and_then(Json::as_str)
                .unwrap_or("");
            match kind {
                "claim" if objective == self.cfg.objective_id => {
                    let Some(artifact) = payload.get("artifact") else {
                        continue;
                    };
                    let submitter = payload
                        .get("submitter")
                        .and_then(Json::as_str)
                        .unwrap_or("?");
                    let Some(rec) = record_from_artifact(artifact) else {
                        continue;
                    };
                    let mut dps = vec![rec.clone()];
                    if !ctx.spec.negation_map {
                        if let Ok(twin) = negated(ctx, &rec) {
                            dps.push(twin);
                        }
                    }
                    let ci = CheckIn {
                        version: PROTOCOL_VERSION,
                        job_id: ctx.job_id.clone(),
                        peer: format!("cairn:{submitter}"),
                        seq,
                        time: now_secs(),
                        units: Vec::new(),
                        dps,
                        solution: None,
                    };
                    match state.apply(ctx, &ci, now_secs(), true) {
                        Ok(out) => {
                            // The twin is bookkeeping, not a second point.
                            let accepted = usize::from(out.accepted_dps > 0);
                            rep.accepted_dps += accepted;
                            rep.rejected_dps += usize::from(out.accepted_dps == 0);
                            rep.solved_now |= out.solved_now;
                            if accepted > 0 {
                                self.log_keys.insert(artifact_key(artifact));
                            }
                        }
                        Err(_) => rep.rejected_dps += 1,
                    }
                }
                "settlement" if objective == self.cfg.objective_id => {
                    if payload.get("submitter").and_then(Json::as_str) == Some(&me) {
                        self.stats.paid_units += 1;
                        self.stats.paid_total +=
                            payload.get("reward").and_then(Json::as_u64).unwrap_or(0);
                    }
                }
                "verdict" => {
                    let claim = payload.get("claim_id").and_then(Json::as_str).unwrap_or("");
                    let status = payload
                        .get("verdict")
                        .and_then(|v| v.get("status"))
                        .and_then(Json::as_str);
                    if self.revealed.contains(claim) && status == Some("reject") {
                        self.stats.rejected += 1;
                    }
                }
                _ => {}
            }
        }
        self.stats.log_dps += rep.accepted_dps as u64;
        self.stats.log_rejected += rep.rejected_dps as u64;
        if max_seq > self.st.last_seq {
            self.st.last_seq = max_seq;
        }
        if self.commit_answer(state)? {
            eprintln!("[cairn] solution committed to the answer objective");
        }
        let (revealed, refused) = self.reveal_due()?;
        rep.revealed = revealed;
        rep.refused = refused;
        self.save()?;
        Ok(rep)
    }

    fn post(&self, path: &str, record: &Json) -> Result<(u16, String), String> {
        let body = canonical(record)?;
        http_request(&self.cfg.url, "POST", path, Some(body.as_bytes()))
    }

    fn get(&self, path: &str) -> Result<(u16, String), String> {
        http_request(&self.cfg.url, "GET", path, None)
    }
}

/// What identifies a claim's work on the cairn side: the whole artifact,
/// coefficients included.  Not the point alone -- a second coefficient
/// pair for a point already in the log is a *novel* artifact there, and
/// it is the collision that solves the instance, so it must go out.
fn artifact_key(artifact: &Json) -> String {
    canonical(artifact).unwrap_or_default()
}

// ── a small HTTP/1.1 client ─────────────────────────────────────────────────

/// One request over a fresh connection (`Connection: close`).  Enough for
/// cairn's server, which answers with `content-length` and never chunks.
/// Plain HTTP only: cairn says to put TLS in a reverse proxy, and this
/// client is meant for a node you run or one on your own network.
pub fn http_request(
    base: &str,
    method: &str,
    path: &str,
    body: Option<&[u8]>,
) -> Result<(u16, String), String> {
    let rest = base
        .strip_prefix("http://")
        .ok_or_else(|| format!("{base}: only http:// URLs are supported"))?;
    let host_port = rest.trim_end_matches('/');
    let host_port = host_port.split('/').next().unwrap_or(host_port);
    let addr = if host_port.contains(':') {
        host_port.to_string()
    } else {
        format!("{host_port}:80")
    };
    let sock = addr
        .to_socket_addrs()
        .map_err(|e| format!("{addr}: {e}"))?
        .next()
        .ok_or_else(|| format!("{addr}: no address"))?;
    let mut stream = TcpStream::connect_timeout(&sock, Duration::from_secs(10))
        .map_err(|e| format!("{addr}: {e}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(60)))
        .map_err(|e| e.to_string())?;
    let mut req = format!("{method} {path} HTTP/1.1\r\nHost: {host_port}\r\nConnection: close\r\n");
    if let Some(b) = body {
        req.push_str(&format!(
            "Content-Type: application/json\r\nContent-Length: {}\r\n",
            b.len()
        ));
    }
    req.push_str("\r\n");
    stream
        .write_all(req.as_bytes())
        .map_err(|e| e.to_string())?;
    if let Some(b) = body {
        stream.write_all(b).map_err(|e| e.to_string())?;
    }
    stream.flush().map_err(|e| e.to_string())?;

    let mut reader = BufReader::new(stream);
    let mut status_line = String::new();
    reader
        .read_line(&mut status_line)
        .map_err(|e| e.to_string())?;
    let status: u16 = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .ok_or_else(|| format!("bad status line {status_line:?}"))?;
    let mut content_length: Option<usize> = None;
    let mut chunked = false;
    loop {
        let mut line = String::new();
        let n = reader.read_line(&mut line).map_err(|e| e.to_string())?;
        if n == 0 || line == "\r\n" || line == "\n" {
            break;
        }
        if let Some((name, value)) = line.split_once(':') {
            let name = name.trim().to_ascii_lowercase();
            let value = value.trim();
            if name == "content-length" {
                content_length = value.parse().ok();
            } else if name == "transfer-encoding" && value.to_ascii_lowercase().contains("chunked")
            {
                chunked = true;
            }
        }
    }
    let mut out = Vec::new();
    if chunked {
        loop {
            let mut size_line = String::new();
            reader
                .read_line(&mut size_line)
                .map_err(|e| e.to_string())?;
            let size = usize::from_str_radix(size_line.trim().split(';').next().unwrap_or("0"), 16)
                .map_err(|e| format!("bad chunk size {size_line:?}: {e}"))?;
            if size == 0 {
                break;
            }
            let mut chunk = vec![0u8; size];
            reader.read_exact(&mut chunk).map_err(|e| e.to_string())?;
            out.extend_from_slice(&chunk);
            let mut crlf = String::new();
            reader.read_line(&mut crlf).map_err(|e| e.to_string())?;
        }
    } else if let Some(n) = content_length {
        out.resize(n, 0);
        reader.read_exact(&mut out).map_err(|e| e.to_string())?;
    } else {
        reader.read_to_end(&mut out).map_err(|e| e.to_string())?;
    }
    Ok((status, String::from_utf8_lossy(&out).into_owned()))
}

#[cfg(test)]
mod tests {
    use super::super::job::{demo_curve, JobSpec};
    use super::super::worker::{run_lane, LaneOptions};
    use super::*;
    use crate::ecc::ed25519::ed25519_verify;
    use std::net::TcpListener;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Arc, Mutex};

    // ── pinned against cairn's frozen conformance/vectors.json ──────────

    #[test]
    fn canonical_encoding_matches_cairns_frozen_vectors() {
        let cases: Vec<(Json, &str, &str)> = vec![
            (json!({}), "{}", "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
            (json!({"b": 2, "a": 1}), "{\"a\":1,\"b\":2}", "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"),
            (
                json!({"i64max": 9223372036854775807i64, "i64min": -9223372036854775808i64, "neg": -5}),
                "{\"i64max\":9223372036854775807,\"i64min\":-9223372036854775808,\"neg\":-5}",
                "",
            ),
            (
                json!({"astral": "😀𝔸", "backslash": "a\\b", "cjk": "日本語", "control": "\u{0}\u{1}\u{1f}",
                       "del": "\u{7f}", "empty": "", "latin": "café", "quote": "a\"b",
                       "shorts": "\u{8}\t\n\u{c}\r", "solidus": "a/b"}),
                "{\"astral\":\"😀𝔸\",\"backslash\":\"a\\\\b\",\"cjk\":\"日本語\",\"control\":\"\\u0000\\u0001\\u001f\",\"del\":\"\u{7f}\",\"empty\":\"\",\"latin\":\"café\",\"quote\":\"a\\\"b\",\"shorts\":\"\\b\\t\\n\\f\\r\",\"solidus\":\"a/b\"}",
                "sha256:e876a09497a4bd08b0049c2c9f8a234aa5bd13f28c241ecc6573c5d9afa95046",
            ),
            (
                json!({"unicode_keys_sort": {"b": 1, "a": 2, "é": 3, "A": 4, "Z": 5}}),
                "{\"unicode_keys_sort\":{\"A\":4,\"Z\":5,\"a\":2,\"b\":1,\"é\":3}}",
                "sha256:38d5e620ea9fff572e756630a5eb12996ea683b4f0c636e36001090081249cc9",
            ),
        ];
        for (value, text, dig) in cases {
            assert_eq!(canonical(&value).unwrap(), text);
            if !dig.is_empty() {
                assert_eq!(digest(&value).unwrap(), dig);
            }
        }
        assert!(
            canonical(&json!(1.5)).is_err(),
            "floats are unrepresentable"
        );
    }

    #[test]
    fn commitment_hash_matches_cairns_frozen_vectors() {
        let oid = "sha256:36dc4eb23ddd295b12608a6d84e2b03b48d437ce278105f93143215d260bb711";
        assert_eq!(
            commitment_hash(oid, "alice", &json!({"n": 42}), "n1").unwrap(),
            "sha256:c4b7d428439e598333b066afb7eeddb2dbdc8f1e1a914ed639885740b1d5ff5e"
        );
        assert_eq!(
            commitment_hash(oid, "bob", &json!({"n": 42}), "n1").unwrap(),
            "sha256:26287c0f8f805964d6772500fff3d5600e150977fd3ebb6bec4f8c088f86163d"
        );
        assert!(commitment_hash(oid, "a|b", &json!({}), "n").is_err());
    }

    #[test]
    fn a_commitment_record_has_the_id_cairn_gives_it() {
        // `records.commitments[0]` of cairn's vectors: the id is the digest of
        // the record, `type` included.
        let record = json!({
            "type": "commitment",
            "created_at": "2026-07-28T00:00:00+00:00",
            "hash": "sha256:4a1cf72173356258ac7b068cefa3a29e8e90b0e59c82ceb23207932210e1cf13",
            "objective_id": "sha256:36dc4eb23ddd295b12608a6d84e2b03b48d437ce278105f93143215d260bb711",
            "submitter": "alice",
        });
        assert_eq!(
            digest(&record).unwrap(),
            "sha256:e86a6262807b107542f64d05900e54906dbebdd1a0e48e2e8d812b06bb900c28"
        );
    }

    #[test]
    fn a_claim_record_has_the_id_and_artifact_id_cairn_gives_it() {
        // `records.claims[0]` of cairn's vectors.
        let oid = "sha256:36dc4eb23ddd295b12608a6d84e2b03b48d437ce278105f93143215d260bb711";
        let record = json!({
            "type": "claim",
            "artifact": {"n": 42},
            "cites": [],
            "created_at": "2026-07-28T00:00:00+00:00",
            "nonce": "nonce-1",
            "objective_id": oid,
            "submitter": "alice",
        });
        assert_eq!(
            digest(&record).unwrap(),
            "sha256:51b216380d88cf32e1e179dc8c52336c26e2aac447045dc4079f3a24bdeb334e"
        );
        assert_eq!(
            digest(&json!({"objective_id": oid, "artifact": {"n": 42}})).unwrap(),
            "sha256:49620d2cbd95777da46e1c3d34793a4926d2f61f6ca2121bac91011e8613de4e"
        );
        assert_eq!(
            commitment_hash(oid, "alice", &json!({"n": 42}), "nonce-1").unwrap(),
            "sha256:4a1cf72173356258ac7b068cefa3a29e8e90b0e59c82ceb23207932210e1cf13"
        );
    }

    #[test]
    fn timestamps_and_epochs_match_cairn() {
        assert_eq!(format_utc(1_785_196_800), "2026-07-28T00:00:00+00:00");
        assert_eq!(format_utc(0), "1970-01-01T00:00:00+00:00");
        assert_eq!(format_utc(951_782_400), "2000-02-29T00:00:00+00:00");
        assert_eq!(
            format_utc(1_785_196_800 + 3661),
            "2026-07-28T01:01:01+00:00"
        );
        assert_eq!(epoch_of(1_785_196_800, 600), 2_975_328);
        assert_eq!(epoch_of(5, 0), 0);
    }

    // ── artifacts ──────────────────────────────────────────────────────

    fn job(curve: &str, secret: u32, dp_bits: u8, negation: bool) -> JobContext {
        let curve = demo_curve(curve).unwrap();
        let q = curve
            .generator()
            .scalar_mul(&BigUint::from(secret), &curve.a_fe());
        let mut spec = JobSpec::new(&curve, &q, "cairn-test", 3).unwrap();
        spec.dp_bits = dp_bits;
        spec.unit_size = 8;
        spec.negation_map = negation;
        spec.build().unwrap()
    }

    fn first_dp(ctx: &JobContext) -> DpRecord {
        (0..200u64)
            .find_map(|i| match super::super::walk::run_walker(ctx, i) {
                super::super::walk::WalkerOutcome::Dp(r) => Some(r),
                _ => None,
            })
            .expect("a walker reaches a DP")
    }

    #[test]
    fn an_artifact_is_canonical_whichever_record_produced_it() {
        let ctx = job("demo-mid", 4242, 3, false);
        let rec = first_dp(&ctx);
        let art = canonical_artifact(&ctx, &rec).unwrap();
        let y = parse_hex(art["y"].as_str().unwrap()).unwrap();
        assert!(&y << 1 <= ctx.p, "canonical y has 2y <= p");
        // The negated record spells the same artifact.
        let twin = negated(&ctx, &rec).unwrap();
        assert_eq!(canonical_artifact(&ctx, &twin).unwrap(), art);
        // Both the artifact and its twin verify as records.
        let back = record_from_artifact(&art).unwrap();
        back.verify(&ctx).expect("the canonical record verifies");
        negated(&ctx, &back)
            .unwrap()
            .verify(&ctx)
            .expect("its twin verifies");
        assert!(record_from_artifact(&json!({"x": "1"})).is_none());
    }

    // ── a fake cairn node ───────────────────────────────────────────────

    /// Enough of `cairn serve --queue` to exercise the transport: `POST
    /// /submit` validates shape and signature and spools; `drain` admits
    /// spooled records to the log in order, refusing a claim whose
    /// commitment is not already in the log; `GET /log` serves the log.
    struct FakeCairn {
        addr: String,
        spool: Arc<Mutex<Vec<Json>>>,
        log: Arc<Mutex<Vec<Json>>>,
    }

    impl FakeCairn {
        fn start() -> Self {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let addr = format!("http://{}", listener.local_addr().unwrap());
            let spool = Arc::new(Mutex::new(Vec::new()));
            let log = Arc::new(Mutex::new(Vec::new()));
            let (s2, l2) = (Arc::clone(&spool), Arc::clone(&log));
            std::thread::spawn(move || {
                for stream in listener.incoming().flatten() {
                    let _ = Self::handle(stream, &s2, &l2);
                }
            });
            Self { addr, spool, log }
        }

        fn handle(
            stream: TcpStream,
            spool: &Mutex<Vec<Json>>,
            log: &Mutex<Vec<Json>>,
        ) -> std::io::Result<()> {
            let mut writer = stream.try_clone()?;
            let mut reader = BufReader::new(stream);
            let mut request = String::new();
            reader.read_line(&mut request)?;
            let mut parts = request.split_whitespace();
            let (method, path) = (
                parts.next().unwrap_or("").to_string(),
                parts.next().unwrap_or("").to_string(),
            );
            let mut length = 0usize;
            loop {
                let mut line = String::new();
                if reader.read_line(&mut line)? == 0 || line == "\r\n" {
                    break;
                }
                if let Some(v) = line.to_ascii_lowercase().strip_prefix("content-length:") {
                    length = v.trim().parse().unwrap_or(0);
                }
            }
            let mut body = vec![0u8; length];
            reader.read_exact(&mut body)?;
            let (status, reply) = match (method.as_str(), path.as_str()) {
                ("GET", "/log") => {
                    let text: String = log
                        .lock()
                        .unwrap()
                        .iter()
                        .map(|e| serde_json::to_string(e).unwrap() + "\n")
                        .collect();
                    (200, text)
                }
                ("POST", p) if p.starts_with("/submit") => match Self::accept(&body) {
                    Ok(record) => {
                        spool.lock().unwrap().push(record.clone());
                        (202, json!({"queued": digest(&record).unwrap(), "note": "Queued, not admitted."}).to_string())
                    }
                    Err(why) => (400, json!({"error": why}).to_string()),
                },
                _ => (404, "{}".to_string()),
            };
            let reason = match status {
                200 => "OK",
                202 => "Accepted",
                400 => "Bad Request",
                _ => "Not Found",
            };
            write!(
                writer,
                "HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                reply.len()
            )?;
            writer.write_all(reply.as_bytes())?;
            writer.flush()
        }

        /// The boundary checks `serve.rs` makes: shape, and a signature
        /// under a key-shaped submitter.
        fn accept(body: &[u8]) -> Result<Json, String> {
            let record: Json = serde_json::from_slice(body).map_err(|e| e.to_string())?;
            let kind = record["type"].as_str().ok_or("no type")?;
            let need: &[&str] = match kind {
                "commitment" => &["objective_id", "submitter", "hash", "created_at"],
                "claim" => &[
                    "objective_id",
                    "submitter",
                    "artifact",
                    "nonce",
                    "created_at",
                    "cites",
                ],
                _ => return Err(format!("unknown kind {kind}")),
            };
            for field in need {
                if record.get(field).is_none() {
                    return Err(format!("missing {field}"));
                }
            }
            let submitter = record["submitter"].as_str().unwrap();
            let is_key = submitter.len() == 64
                && submitter
                    .bytes()
                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase());
            match (is_key, record.get("signature").and_then(Json::as_str)) {
                (false, None) => {}
                (false, Some(_)) => return Err("a nickname may not carry a signature".into()),
                (true, None) => return Err("a key must sign".into()),
                (true, Some(sig)) => {
                    let mut payload = record.clone();
                    payload.as_object_mut().unwrap().remove("signature");
                    let pk: [u8; 32] = hex::decode(submitter).unwrap().try_into().unwrap();
                    let sig: [u8; 64] = hex::decode(sig)
                        .map_err(|e| e.to_string())?
                        .try_into()
                        .map_err(|_| "bad signature length".to_string())?;
                    if !ed25519_verify(canonical(&payload)?.as_bytes(), &pk, &sig) {
                        return Err("bad signature".into());
                    }
                }
            }
            Ok(record)
        }

        /// Admit the spool to the log, in order.  Returns what was refused.
        fn drain(&self) -> Vec<String> {
            let records: Vec<Json> = std::mem::take(&mut *self.spool.lock().unwrap());
            let mut refused = Vec::new();
            let mut log = self.log.lock().unwrap();
            for record in records {
                let kind = record["type"].as_str().unwrap().to_string();
                let mut payload = record.clone();
                payload.as_object_mut().unwrap().remove("type");
                if kind == "claim" {
                    let hash = commitment_hash(
                        payload["objective_id"].as_str().unwrap(),
                        payload["submitter"].as_str().unwrap(),
                        &payload["artifact"],
                        payload["nonce"].as_str().unwrap(),
                    )
                    .unwrap();
                    let committed = log
                        .iter()
                        .any(|e| e["kind"] == "commitment" && e["payload"]["hash"] == hash);
                    if !committed {
                        refused.push("reveal without a commitment".into());
                        continue;
                    }
                }
                let seq = log.len() as u64 + 1;
                log.push(json!({"seq": seq, "kind": kind, "payload": payload, "ts": "2026-07-28T00:00:00+00:00"}));
            }
            refused
        }

        fn log(&self) -> Vec<Json> {
            self.log.lock().unwrap().clone()
        }
    }

    fn transport(
        fake: &FakeCairn,
        who: Submitter,
        clock: &Arc<AtomicU64>,
        answer: Option<&str>,
    ) -> CairnTransport {
        let clock = Arc::clone(clock);
        CairnTransport::open(CairnConfig {
            url: fake.addr.clone(),
            objective_id: "sha256:objective".into(),
            submitter: who,
            answer_objective: answer.map(String::from),
            epoch_secs: 10,
            state_path: None,
            clock: Arc::new(move || clock.load(Ordering::Relaxed)),
        })
        .unwrap()
    }

    fn lane_round(
        ctx: &JobContext,
        state: &Mutex<SharedState>,
        transport: &Mutex<CairnTransport>,
        lane: &str,
    ) {
        run_lane(
            ctx,
            state,
            &LaneOptions {
                max_walkers: 8,
                checkin_every: 4,
                claim_window: 1,
                ..LaneOptions::new(lane)
            },
            &mut |ci| {
                transport.lock().unwrap().publish(ctx, ci).expect("publish");
            },
            &|| false,
        );
    }

    #[test]
    fn points_travel_through_cairn_as_commit_reveal_claims_and_solve() {
        let fake = FakeCairn::start();
        let ctx = job("demo-small", 0x1a2b, 2, false);
        let clock = Arc::new(AtomicU64::new(1_785_196_800));
        let secret = BigUint::from(0x1a2bu32);

        let a_state = Mutex::new(SharedState::new(&ctx));
        let b_state = Mutex::new(SharedState::new(&ctx));
        let a = Mutex::new(transport(
            &fake,
            Submitter::Nickname("alice".into()),
            &clock,
            Some("sha256:answer"),
        ));
        let b = Mutex::new(transport(
            &fake,
            Submitter::Nickname("bob".into()),
            &clock,
            Some("sha256:answer"),
        ));

        let mut rounds = 0;
        loop {
            rounds += 1;
            // Each node walks its own units and commits what it found.
            lane_round(&ctx, &a_state, &a, "alice.0");
            lane_round(&ctx, &b_state, &b, "bob.0");
            assert!(fake.drain().is_empty());
            // The epoch turns; syncing reveals, and the operator admits.
            clock.fetch_add(10, Ordering::Relaxed);
            a.lock()
                .unwrap()
                .sync(&ctx, &mut a_state.lock().unwrap())
                .unwrap();
            b.lock()
                .unwrap()
                .sync(&ctx, &mut b_state.lock().unwrap())
                .unwrap();
            assert!(
                fake.drain().is_empty(),
                "every reveal opens a commitment already in the log"
            );
            // Everyone reads the log: the other node's points arrive.
            a.lock()
                .unwrap()
                .sync(&ctx, &mut a_state.lock().unwrap())
                .unwrap();
            b.lock()
                .unwrap()
                .sync(&ctx, &mut b_state.lock().unwrap())
                .unwrap();
            let solved = a_state.lock().unwrap().solution.is_some()
                && b_state.lock().unwrap().solution.is_some();
            if solved {
                break;
            }
            assert!(rounds < 60, "no solution after {rounds} rounds");
        }
        assert_eq!(a_state.lock().unwrap().solution, Some(secret.clone()));
        assert_eq!(b_state.lock().unwrap().solution, Some(secret));

        // The log holds a canonical artifact per accepted claim, each one
        // opening a commitment with the hash cairn would compute.
        let log = fake.log();
        let claims: Vec<&Json> = log
            .iter()
            .filter(|e| e["kind"] == "claim" && e["payload"]["objective_id"] == "sha256:objective")
            .collect();
        assert!(claims.len() >= 2, "{}", claims.len());
        for c in &claims {
            let art = &c["payload"]["artifact"];
            let y = parse_hex(art["y"].as_str().unwrap()).unwrap();
            assert!(&y << 1 <= ctx.p);
            record_from_artifact(art)
                .unwrap()
                .verify(&ctx)
                .expect("a claimed point verifies");
        }
        // Whoever's merge solved it committed k to the answer objective, and
        // revealed it once the epoch turned.
        clock.fetch_add(10, Ordering::Relaxed);
        a.lock()
            .unwrap()
            .sync(&ctx, &mut a_state.lock().unwrap())
            .unwrap();
        b.lock()
            .unwrap()
            .sync(&ctx, &mut b_state.lock().unwrap())
            .unwrap();
        assert!(fake.drain().is_empty());
        let answer_claims = fake
            .log()
            .into_iter()
            .filter(|e| e["kind"] == "claim" && e["payload"]["objective_id"] == "sha256:answer")
            .count();
        assert!(
            answer_claims >= 1,
            "the solution was claimed on the answer objective"
        );
        let k = fake
            .log()
            .into_iter()
            .find(|e| e["kind"] == "claim" && e["payload"]["objective_id"] == "sha256:answer")
            .unwrap();
        assert_eq!(
            k["payload"]["artifact"]["k"].as_str().unwrap(),
            format!("{:064x}", 0x1a2b)
        );

        // A node with no points of its own still learns the solution from
        // the log, and a resubmitted point is skipped rather than paid for twice.
        let c_state = Mutex::new(SharedState::new(&ctx));
        let mut c = transport(&fake, Submitter::Nickname("carol".into()), &clock, None);
        let rep = c.sync(&ctx, &mut c_state.lock().unwrap()).unwrap();
        assert!(rep.accepted_dps >= 2);
        assert_eq!(rep.rejected_dps, 0);
        assert!(c_state.lock().unwrap().solution.is_some());
        let repeat = CheckIn {
            version: PROTOCOL_VERSION,
            job_id: ctx.job_id.clone(),
            peer: "carol.0".into(),
            seq: 1,
            time: 0,
            units: Vec::new(),
            dps: vec![record_from_artifact(&claims[0]["payload"]["artifact"]).unwrap()],
            solution: None,
        };
        let rep = c.publish(&ctx, &repeat).unwrap();
        assert_eq!(
            rep,
            PublishReport {
                committed: 0,
                skipped: 1
            }
        );
    }

    #[test]
    fn a_key_submitter_signs_what_cairn_verifies() {
        let fake = FakeCairn::start();
        let ctx = job("demo-mid", 4242, 3, true);
        let clock = Arc::new(AtomicU64::new(1_785_196_800));
        let mut seed = [0u8; 32];
        crate::utils::random_bytes(&mut seed);
        let public_hex = hex::encode(ed25519_pubkey(&seed));
        let mut t = transport(
            &fake,
            Submitter::Key {
                seed,
                public_hex: public_hex.clone(),
            },
            &clock,
            None,
        );
        let rec = first_dp(&ctx);
        let ci = CheckIn {
            version: PROTOCOL_VERSION,
            job_id: ctx.job_id.clone(),
            peer: "k.0".into(),
            seq: 1,
            time: 0,
            units: Vec::new(),
            dps: vec![rec],
            solution: None,
        };
        assert_eq!(t.publish(&ctx, &ci).unwrap().committed, 1);
        assert!(
            fake.drain().is_empty(),
            "the fake node verified the commitment's signature"
        );
        // Not yet: same epoch as the commitment.
        let mut state = SharedState::new(&ctx);
        assert_eq!(t.sync(&ctx, &mut state).unwrap().revealed, 0);
        assert_eq!(t.pending(), 1);
        clock.fetch_add(10, Ordering::Relaxed);
        assert_eq!(t.sync(&ctx, &mut state).unwrap().revealed, 1);
        assert!(fake.drain().is_empty());
        let log = fake.log();
        let claim = log.iter().find(|e| e["kind"] == "claim").unwrap();
        assert_eq!(claim["payload"]["submitter"], public_hex);
        let sig: [u8; 64] = hex::decode(claim["payload"]["signature"].as_str().unwrap())
            .unwrap()
            .try_into()
            .unwrap();
        let mut payload = claim["payload"].clone();
        payload.as_object_mut().unwrap().remove("signature");
        payload["type"] = json!("claim");
        let pk: [u8; 32] = hex::decode(&public_hex).unwrap().try_into().unwrap();
        assert!(ed25519_verify(
            canonical(&payload).unwrap().as_bytes(),
            &pk,
            &sig
        ));
    }

    #[test]
    fn pending_commitments_survive_a_restart() {
        let fake = FakeCairn::start();
        let ctx = job("demo-mid", 4242, 3, false);
        let clock = Arc::new(AtomicU64::new(1_785_196_800));
        let dir = std::env::temp_dir().join(format!(
            "crypto-cairn-{}-{}",
            std::process::id(),
            clock.load(Ordering::Relaxed)
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("state.json");
        let cfg = || CairnConfig {
            url: fake.addr.clone(),
            objective_id: "sha256:objective".into(),
            submitter: Submitter::Nickname("dave".into()),
            answer_objective: None,
            epoch_secs: 10,
            state_path: Some(path.clone()),
            clock: {
                let c = Arc::clone(&clock);
                Arc::new(move || c.load(Ordering::Relaxed))
            },
        };
        let rec = first_dp(&ctx);
        let ci = CheckIn {
            version: PROTOCOL_VERSION,
            job_id: ctx.job_id.clone(),
            peer: "dave.0".into(),
            seq: 1,
            time: 0,
            units: Vec::new(),
            dps: vec![rec.clone()],
            solution: None,
        };
        {
            let mut t = CairnTransport::open(cfg()).unwrap();
            assert_eq!(t.publish(&ctx, &ci).unwrap().committed, 1);
        }
        fake.drain();
        clock.fetch_add(10, Ordering::Relaxed);
        let mut t = CairnTransport::open(cfg()).unwrap();
        assert_eq!(t.pending(), 1, "the commitment was reloaded");
        let mut state = SharedState::new(&ctx);
        assert_eq!(t.sync(&ctx, &mut state).unwrap().revealed, 1);
        assert!(fake.drain().is_empty());
        // And the point is remembered as submitted after the restart too.
        assert_eq!(
            t.publish(&ctx, &ci).unwrap(),
            PublishReport {
                committed: 0,
                skipped: 1
            }
        );
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn the_client_speaks_enough_http() {
        let fake = FakeCairn::start();
        let (status, body) = http_request(&fake.addr, "GET", "/log", None).unwrap();
        assert_eq!((status, body.as_str()), (200, ""));
        let (status, _) = http_request(&fake.addr, "GET", "/nope", None).unwrap();
        assert_eq!(status, 404);
        assert!(http_request("https://x", "GET", "/", None).is_err());
    }
}
