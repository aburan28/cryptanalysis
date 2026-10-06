//! Shared-directory transport.
//!
//! The lowest-tech way to collaborate: every peer appends its
//! check-ins as files to one directory and reads everyone else's.
//! Anything that replicates a directory — NFS, Syncthing, Dropbox,
//! `rsync` in a cron job, a git repository — becomes the network.
//!
//! ```text
//! <dir>/job.json                  the JobSpec
//! <dir>/checkins/<peer>-<seq>.json one CheckIn each, written atomically
//! ```
//!
//! Files are immutable once renamed into place, and the merge is
//! idempotent, so partial syncs, re-syncs and re-reads are harmless.

use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

use super::job::{JobContext, JobSpec};
use super::state::{now_secs, CheckIn, SharedState};

pub struct Mailbox {
    dir: PathBuf,
    seen_files: HashSet<String>,
}

impl Mailbox {
    pub fn open(dir: &Path) -> std::io::Result<Self> {
        fs::create_dir_all(dir.join("checkins"))?;
        Ok(Self {
            dir: dir.to_path_buf(),
            seen_files: HashSet::new(),
        })
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    pub fn write_job(&self, spec: &JobSpec) -> std::io::Result<()> {
        fs::write(self.dir.join("job.json"), spec.to_json())
    }

    pub fn read_job(dir: &Path) -> Result<JobSpec, String> {
        let s = fs::read_to_string(dir.join("job.json"))
            .map_err(|e| format!("{}: {e}", dir.join("job.json").display()))?;
        JobSpec::from_json(&s)
    }

    /// Publish one check-in (write to a temp name, then rename).  The
    /// file is marked as seen so the next [`sync`](Self::sync) does
    /// not re-read our own output.
    pub fn publish(&mut self, ci: &CheckIn) -> std::io::Result<()> {
        let name = format!("{}-{:012}.json", sanitize(&ci.peer), ci.seq);
        let tmp = self.dir.join("checkins").join(format!(".{name}.tmp"));
        let fin = self.dir.join("checkins").join(&name);
        fs::write(&tmp, serde_json::to_vec(ci)?)?;
        fs::rename(&tmp, &fin)?;
        self.seen_files.insert(name);
        Ok(())
    }

    /// Relay: publish every check-in in `state`'s log that this
    /// mailbox has neither read nor written.  Lets a node that also
    /// gossips over TCP act as a bridge into the directory.  Returns
    /// the number of files written.
    pub fn publish_missing(&mut self, state: &SharedState) -> std::io::Result<usize> {
        let mut written = 0;
        for ci in state.delta_for(&Default::default()) {
            let name = format!("{}-{:012}.json", sanitize(&ci.peer), ci.seq);
            if self.seen_files.contains(&name) {
                continue;
            }
            self.publish(&ci)?;
            written += 1;
        }
        Ok(written)
    }

    /// Merge every check-in file not yet read into `state`.  Returns
    /// `(files merged, dps rejected)`.
    pub fn sync(
        &mut self,
        ctx: &JobContext,
        state: &mut SharedState,
    ) -> std::io::Result<(usize, usize)> {
        let mut names: Vec<String> = Vec::new();
        for entry in fs::read_dir(self.dir.join("checkins"))? {
            let entry = entry?;
            let name = entry.file_name().to_string_lossy().into_owned();
            if name.starts_with('.') || !name.ends_with(".json") || self.seen_files.contains(&name)
            {
                continue;
            }
            names.push(name);
        }
        names.sort();
        let mut merged = 0;
        let mut rejected = 0;
        for name in names {
            let path = self.dir.join("checkins").join(&name);
            let bytes = match fs::read(&path) {
                Ok(b) => b,
                Err(_) => continue, // being written / removed; retry next sync
            };
            let ci: CheckIn = match serde_json::from_slice(&bytes) {
                Ok(c) => c,
                Err(_) => {
                    self.seen_files.insert(name);
                    continue;
                }
            };
            self.seen_files.insert(name);
            if let Ok(out) = state.apply(ctx, &ci, now_secs(), true) {
                if out.new {
                    merged += 1;
                }
                rejected += out.rejected_dps;
            }
        }
        Ok((merged, rejected))
    }
}

fn sanitize(peer: &str) -> String {
    peer.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '.' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::super::job::{demo_curve, JobSpec, PROTOCOL_VERSION};
    use super::super::worker::{run_lane, LaneOptions};
    use super::*;
    use num_bigint::BigUint;
    use std::sync::Mutex;

    pub(crate) fn temp_dir(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!(
            "pollard-collab-{tag}-{}-{}",
            std::process::id(),
            now_secs()
        ));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn two_peers_collaborate_through_a_directory() {
        let curve = demo_curve("demo-mid").unwrap();
        let secret = BigUint::from(42_424u32);
        let q = curve.generator().scalar_mul(&secret, &curve.a_fe());
        let mut spec = JobSpec::new(&curve, &q, "mailbox", 5).unwrap();
        spec.dp_bits = 3;
        spec.unit_size = 16;
        let dir = temp_dir("mbox");
        Mailbox::open(&dir).unwrap().write_job(&spec).unwrap();

        // Two independent processes' worth of state, sharing only the dir.
        let read_back = Mailbox::read_job(&dir).unwrap();
        assert_eq!(read_back, spec);
        let ctx = read_back.build().unwrap();
        let mut peers: Vec<(Mailbox, Mutex<SharedState>)> = (0..2)
            .map(|_| {
                (
                    Mailbox::open(&dir).unwrap(),
                    Mutex::new(SharedState::new(&ctx)),
                )
            })
            .collect();

        // Alternate: each peer works a small walker budget, publishes,
        // then syncs.  Neither peer alone gets enough budget per round
        // to be sure of solving; together they converge.
        let mut rounds = 0;
        loop {
            rounds += 1;
            for (i, (mbox, state)) in peers.iter_mut().enumerate() {
                let mut published = Vec::new();
                run_lane(
                    &ctx,
                    state,
                    &LaneOptions {
                        max_walkers: 16,
                        checkin_every: 8,
                        claim_window: 1,
                        ..LaneOptions::new(&format!("p{i}.0"))
                    },
                    &mut |ci| published.push(ci.clone()),
                    &|| false,
                );
                for ci in &published {
                    mbox.publish(ci).unwrap();
                }
                mbox.sync(&ctx, state.get_mut().unwrap()).unwrap();
            }
            let solved = peers
                .iter()
                .all(|(_, s)| s.lock().unwrap().solution.is_some());
            if solved {
                break;
            }
            assert!(rounds < 200, "no convergence");
        }
        for (_, s) in &peers {
            assert_eq!(s.lock().unwrap().solution, Some(secret.clone()));
        }
        // Both peers saw both peers' work, and nobody rejected anything.
        for (_, s) in &peers {
            let st = s.lock().unwrap();
            assert_eq!(st.version_vector().len(), 2);
            assert_eq!(st.rejected_dps, 0);
        }
        // A third party bridging in a state it got elsewhere only
        // writes what the directory lacks.
        let mut bridge = Mailbox::open(&dir).unwrap();
        let mut fresh = SharedState::new(&ctx);
        bridge.sync(&ctx, &mut fresh).unwrap();
        assert_eq!(bridge.publish_missing(&fresh).unwrap(), 0);
        let mut extra = CheckIn {
            version: PROTOCOL_VERSION,
            job_id: ctx.job_id.clone(),
            peer: "elsewhere.0".into(),
            seq: 1,
            time: 0,
            units: vec![],
            dps: vec![],
            solution: None,
        };
        fresh.apply(&ctx, &extra, 0, true).unwrap();
        assert_eq!(bridge.publish_missing(&fresh).unwrap(), 1);
        extra.seq = 2;
        fresh.apply(&ctx, &extra, 0, true).unwrap();
        assert_eq!(bridge.publish_missing(&fresh).unwrap(), 1);
        let mut reader = Mailbox::open(&dir).unwrap();
        let mut seen = SharedState::new(&ctx);
        reader.sync(&ctx, &mut seen).unwrap();
        assert_eq!(seen.version_vector()["elsewhere.0"], 2);
        let _ = fs::remove_dir_all(&dir);
    }
}
