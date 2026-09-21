//! # Collaborative (peer-to-peer) Pollard rho
//!
//! Lets any number of machines, owned by different people, work on
//! one ECDLP instance together: the search space is divided into
//! work units nobody has to hand out, progress is checked in as
//! self-verifying distinguished points, and every peer can merge
//! every other peer's check-ins without a coordinator.
//!
//! The full design rationale lives in
//! `docs/POLLARD_COLLAB_DESIGN.md`; this is the short version.
//!
//! ## The three ideas
//!
//! 1. **Deterministic walks, indexed starts.**  The job document
//!    ([`job::JobSpec`]) fixes curve, `P`, `Q`, `dp_bits` and a seed.
//!    Its hash — the job id — seeds a PRF that derives the
//!    `r`-adding branch table and the start point of *walker `i`* for
//!    every `i ∈ [0, 2⁶⁴)`.  A **work unit** is a contiguous range of
//!    walker indices.  So "dividing the search space" is just
//!    agreeing on integers: peers with disjoint ranges never repeat a
//!    trail, and any walker can be re-run to audit a claim.  Because
//!    everyone uses the same walk function, a collision between any
//!    two peers' trails still solves the instance — the parallel
//!    speed-up of van Oorschot–Wiener is preserved.
//!
//! 2. **Check-ins are self-certifying facts.**  A [`state::CheckIn`]
//!    carries distinguished points as `(walker, steps, x, y, a, b)`
//!    with `a·P + b·Q = (x, y)`, plus a cumulative progress cursor for
//!    the unit being worked.  A receiver verifies each DP with two
//!    scalar multiplications — negligible next to the `2^dp_bits`
//!    steps it stands for — so a dishonest peer can waste only its
//!    own time.
//!
//! 3. **State is a CRDT.**  [`state::SharedState`] is the merge of
//!    all check-ins seen: a grow-only DP set (a repeat key with
//!    different coefficients *is* the collision), per-peer
//!    max-registers for unit progress, a verified write-once
//!    solution, and the check-in log itself keyed by `(peer, seq)`.
//!    Merging is commutative, associative and idempotent, so peers can
//!    exchange logs in any order, over any transport, and converge.
//!    Units are *leased*, not assigned: a claim is live while its
//!    owner keeps checking in; when it goes quiet the next peer
//!    resumes the unit from the last reported walker cursor.
//!
//! ## Transports
//!
//! - [`mailbox`]: a shared directory of JSON files (NFS, Syncthing,
//!   git, rsync — whatever replicates files).
//! - [`net`]: TCP gossip; each node listens and syncs with the peers
//!   it knows, exchanging exactly the check-ins the other side lacks.
//! - [`cairn`]: a paid network.  Points go out as commit–reveal claims
//!   on a cairn *piecework* objective and the objective's log comes back
//!   as the DP table, so every accepted point is paid and every node
//!   that reads the log sees every collision.
//!
//! ## CLI
//!
//! ```text
//! crypto cryptanalysis rho-collab init  --curve demo-mid --secret 1234 --out job.json
//! crypto cryptanalysis rho-collab work  --job job.json --node alice --mailbox ./shared
//! crypto cryptanalysis rho-collab work  --job job.json --node bob --listen 0.0.0.0:7000 --peer alice:7000
//! crypto cryptanalysis rho-collab status --job job.json --mailbox ./shared
//! crypto cryptanalysis rho-collab work  --job nums-50-rho.json --node carol \
//!     --cairn http://127.0.0.1:8080 --objective sha256:… --submitter carol
//! ```

pub mod cairn;
pub mod job;
pub mod mailbox;
pub mod net;
pub mod state;
pub mod walk;
pub mod worker;

pub use job::{demo_curve, JobContext, JobSpec, DEMO_CURVES, PROTOCOL_VERSION};
pub use mailbox::Mailbox;
pub use net::{sync_with_peer, Message, PeerServer, SyncReport};
pub use state::{CheckIn, Progress, SharedState, UnitReport, UnitView};
pub use walk::{run_walker, DpRecord, WalkerOutcome};
pub use worker::{run_lane, LaneOptions, LaneSummary};
