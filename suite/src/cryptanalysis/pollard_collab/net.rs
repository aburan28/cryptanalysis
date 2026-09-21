//! TCP gossip transport — plain `std::net`, one JSON object per line.
//!
//! Every node listens; every node knows some peers.  A *sync* with a
//! peer is two round-trips on one connection:
//!
//! ```text
//! → {"kind":"pull","job_id":…,"known":{peer:seq,…}}
//! ← {"kind":"batch","checkins":[…],"known":{…}}   what I lack; what they have
//! → {"kind":"push","checkins":[…]}                what they lack
//! ← {"kind":"ack","accepted":n,"rejected":m}
//! ```
//!
//! Because the batch carries the responder's version vector, one sync
//! makes the two logs equal.  Any connected peer graph therefore
//! converges after a few rounds — the topology is the operator's
//! choice (a hub everyone syncs with, a ring, a full mesh, …).

use std::collections::BTreeMap;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream, ToSocketAddrs};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use serde::{Deserialize, Serialize};

use super::job::JobContext;
use super::state::{now_secs, CheckIn, SharedState};

/// Wire messages.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Message {
    Pull {
        job_id: String,
        known: BTreeMap<String, u64>,
    },
    Batch {
        checkins: Vec<CheckIn>,
        known: BTreeMap<String, u64>,
        solution: Option<String>,
    },
    Push {
        checkins: Vec<CheckIn>,
    },
    Ack {
        accepted: usize,
        rejected: usize,
    },
    Error {
        message: String,
    },
}

/// Cap on one line (a batch) — guards a listener against garbage.
const MAX_LINE: usize = 64 << 20;

fn send(stream: &mut TcpStream, m: &Message) -> std::io::Result<()> {
    let mut line = serde_json::to_vec(m)?;
    line.push(b'\n');
    stream.write_all(&line)?;
    stream.flush()
}

fn recv(reader: &mut BufReader<TcpStream>) -> std::io::Result<Option<Message>> {
    let mut line = String::new();
    let n = reader.read_line(&mut line)?;
    if n == 0 {
        return Ok(None);
    }
    if line.len() > MAX_LINE {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "line too long",
        ));
    }
    serde_json::from_str(&line)
        .map(Some)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
}

/// Serve one connection until the peer hangs up.
fn handle(stream: TcpStream, ctx: &JobContext, state: &Mutex<SharedState>) -> std::io::Result<()> {
    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
    let mut writer = stream.try_clone()?;
    let mut reader = BufReader::new(stream);
    while let Some(msg) = recv(&mut reader)? {
        let reply = match msg {
            Message::Pull { job_id, known } => {
                if job_id != ctx.job_id {
                    Message::Error {
                        message: "different job".into(),
                    }
                } else {
                    let st = state.lock().unwrap();
                    Message::Batch {
                        checkins: st.delta_for(&known),
                        known: st.version_vector(),
                        solution: st.solution.as_ref().map(super::job::hex_of),
                    }
                }
            }
            Message::Push { checkins } => {
                let mut st = state.lock().unwrap();
                let (mut acc, mut rej) = (0, 0);
                for ci in &checkins {
                    match st.apply(ctx, ci, now_secs(), true) {
                        Ok(o) => {
                            acc += o.accepted_dps;
                            rej += o.rejected_dps;
                        }
                        Err(_) => rej += 1,
                    }
                }
                Message::Ack {
                    accepted: acc,
                    rejected: rej,
                }
            }
            _ => Message::Error {
                message: "unexpected message".into(),
            },
        };
        send(&mut writer, &reply)?;
    }
    Ok(())
}

/// A listening node.  Drop or call [`stop`](Self::stop) to shut down.
pub struct PeerServer {
    addr: std::net::SocketAddr,
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl PeerServer {
    /// Bind `addr` (use port 0 for an ephemeral port) and serve
    /// `state` in a background thread.
    pub fn start(
        addr: impl ToSocketAddrs,
        ctx: Arc<JobContext>,
        state: Arc<Mutex<SharedState>>,
    ) -> std::io::Result<Self> {
        let listener = TcpListener::bind(addr)?;
        listener.set_nonblocking(true)?;
        let local = listener.local_addr()?;
        let stop = Arc::new(AtomicBool::new(false));
        let stop2 = Arc::clone(&stop);
        let handle = std::thread::spawn(move || {
            while !stop2.load(Ordering::Relaxed) {
                match listener.accept() {
                    Ok((stream, _)) => {
                        let _ = stream.set_nonblocking(false);
                        let ctx = Arc::clone(&ctx);
                        let state = Arc::clone(&state);
                        std::thread::spawn(move || {
                            let _ = handle(stream, &ctx, &state);
                        });
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(Duration::from_millis(20));
                    }
                    Err(_) => break,
                }
            }
        });
        Ok(Self {
            addr: local,
            stop,
            handle: Some(handle),
        })
    }

    pub fn local_addr(&self) -> std::net::SocketAddr {
        self.addr
    }

    pub fn stop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }
}

impl Drop for PeerServer {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Result of one sync.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SyncReport {
    pub received: usize,
    pub sent: usize,
    pub rejected_here: usize,
    pub rejected_there: usize,
}

/// Exchange logs with the node at `addr` (pull, then push).
pub fn sync_with_peer(
    addr: impl ToSocketAddrs,
    ctx: &JobContext,
    state: &Mutex<SharedState>,
) -> std::io::Result<SyncReport> {
    let addr = addr
        .to_socket_addrs()?
        .next()
        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::InvalidInput, "no address"))?;
    let stream = TcpStream::connect_timeout(&addr, Duration::from_secs(5))?;
    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
    let mut writer = stream.try_clone()?;
    let mut reader = BufReader::new(stream);
    let mut rep = SyncReport::default();

    let known = state.lock().unwrap().version_vector();
    send(
        &mut writer,
        &Message::Pull {
            job_id: ctx.job_id.clone(),
            known,
        },
    )?;
    let their_known = match recv(&mut reader)? {
        Some(Message::Batch {
            checkins,
            known,
            solution: _,
        }) => {
            let mut st = state.lock().unwrap();
            for ci in &checkins {
                match st.apply(ctx, ci, now_secs(), true) {
                    Ok(o) => {
                        if o.new {
                            rep.received += 1;
                        }
                        rep.rejected_here += o.rejected_dps;
                    }
                    Err(_) => rep.rejected_here += 1,
                }
            }
            known
        }
        Some(Message::Error { message }) => return Err(std::io::Error::other(message)),
        _ => {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "expected batch",
            ))
        }
    };

    let to_send = state.lock().unwrap().delta_for(&their_known);
    rep.sent = to_send.len();
    if !to_send.is_empty() {
        send(&mut writer, &Message::Push { checkins: to_send })?;
        if let Some(Message::Ack { rejected, .. }) = recv(&mut reader)? {
            rep.rejected_there = rejected;
        }
    }
    Ok(rep)
}

#[cfg(test)]
mod tests {
    use super::super::job::{demo_curve, JobSpec};
    use super::super::worker::{run_lane, LaneOptions};
    use super::*;
    use num_bigint::BigUint;

    fn job(secret: u32) -> Arc<JobContext> {
        let curve = demo_curve("demo-mid").unwrap();
        let q = curve
            .generator()
            .scalar_mul(&BigUint::from(secret), &curve.a_fe());
        let mut spec = JobSpec::new(&curve, &q, "net", 8).unwrap();
        spec.dp_bits = 3;
        spec.unit_size = 16;
        Arc::new(spec.build().unwrap())
    }

    #[test]
    fn message_round_trip() {
        let m = Message::Pull {
            job_id: "abc".into(),
            known: BTreeMap::from([("p.0".to_string(), 3u64)]),
        };
        let s = serde_json::to_string(&m).unwrap();
        assert!(s.contains("\"kind\":\"pull\""));
        assert_eq!(serde_json::from_str::<Message>(&s).unwrap(), m);
    }

    #[test]
    fn three_nodes_in_a_chain_converge() {
        let ctx = job(88_888);
        let secret = BigUint::from(88_888u32);
        let nodes: Vec<Arc<Mutex<SharedState>>> = (0..3)
            .map(|_| Arc::new(Mutex::new(SharedState::new(&ctx))))
            .collect();
        let servers: Vec<PeerServer> = nodes
            .iter()
            .map(|s| PeerServer::start("127.0.0.1:0", Arc::clone(&ctx), Arc::clone(s)).unwrap())
            .collect();
        let addrs: Vec<_> = servers.iter().map(|s| s.local_addr()).collect();

        // Chain topology: 0 ↔ 1 ↔ 2.  Node 0 and 2 never talk directly.
        let mut rounds = 0;
        loop {
            rounds += 1;
            for (i, st) in nodes.iter().enumerate() {
                run_lane(
                    &ctx,
                    st,
                    &LaneOptions {
                        max_walkers: 8,
                        checkin_every: 4,
                        claim_window: 1,
                        ..LaneOptions::new(&format!("n{i}.0"))
                    },
                    &mut |_| {},
                    &|| false,
                );
            }
            sync_with_peer(addrs[1], &ctx, &nodes[0]).unwrap();
            sync_with_peer(addrs[1], &ctx, &nodes[2]).unwrap();
            let all = nodes.iter().all(|s| s.lock().unwrap().solution.is_some());
            if all {
                break;
            }
            assert!(rounds < 300, "no convergence");
        }
        // One more sync pass so every node holds the complete log.
        sync_with_peer(addrs[1], &ctx, &nodes[0]).unwrap();
        sync_with_peer(addrs[1], &ctx, &nodes[2]).unwrap();
        sync_with_peer(addrs[1], &ctx, &nodes[0]).unwrap();
        let vvs: Vec<_> = nodes
            .iter()
            .map(|s| s.lock().unwrap().version_vector())
            .collect();
        assert_eq!(vvs[0], vvs[1]);
        assert_eq!(vvs[1], vvs[2]);
        assert_eq!(vvs[0].len(), 3, "every node's lane reached every node");
        for s in &nodes {
            let st = s.lock().unwrap();
            assert_eq!(st.solution, Some(secret.clone()));
            assert_eq!(st.rejected_dps, 0);
        }
        drop(servers);
    }

    #[test]
    fn foreign_job_is_refused() {
        let ctx = job(1);
        let other = job(2);
        let state = Arc::new(Mutex::new(SharedState::new(&ctx)));
        let server =
            PeerServer::start("127.0.0.1:0", Arc::clone(&ctx), Arc::clone(&state)).unwrap();
        let mine = Mutex::new(SharedState::new(&other));
        let err = sync_with_peer(server.local_addr(), &other, &mine).unwrap_err();
        assert!(err.to_string().contains("different job"));
    }
}
