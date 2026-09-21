# Collaborative (peer-to-peer) Pollard rho — design

Module: `src/cryptanalysis/pollard_collab/`.
CLI: `crypto cryptanalysis rho-collab {init, work, status}`.

## 1. Goal

Let many machines, run by different people, attack one elliptic-curve
discrete-log instance `Q = x·P` together, such that

- the search space is divided so participants do not repeat each other's work;
- progress is checked in incrementally and survives peers leaving;
- nobody has to run a coordinator, and a participant who lies can only waste
  their own time;
- the parallel speed-up of van Oorschot–Wiener distinguished-point rho is kept:
  `m` machines finish about `m` times faster than one.

## 2. Background: why plain rho does not divide

Rho finds `x` by walking a pseudo-random function on the group until two
walks collide. The naive way to "divide" it — give every machine its own walk
function — is wrong: collisions only count *within* a walk function, so `m`
machines give no speed-up at all. Van Oorschot–Wiener fix this by having every
machine use the **same** walk function and report only *distinguished points*
(DPs, points whose x-coordinate has `dp_bits` low zero bits). Two trails that
meet anywhere stay merged and reach the same DP, so a table of everyone's DPs
detects a collision between any two machines.

So "dividing the search space" cannot mean partitioning the group. What can be
partitioned is the set of **trail start points**. That is the whole trick.

## 3. Search-space division: indexed walkers

The job document (`JobSpec`) fixes the curve, `P`, `Q`, `n`, `dp_bits`, the
branch count, the negation-map flag, a unit size and a seed. Its SHA-256 is the
**job id**. From the id every peer derives, offline and identically:

| derived object | formula |
|---|---|
| branch `j` of the `r`-adding walk | `B_j = u_j·P + v_j·Q`, `(u_j, v_j) = PRF(id, "branch", j)` |
| start of **walker `i`** | `R_i = a_i·P + b_i·Q`, `(a_i, b_i) = PRF(id, "walker", i)` |

`PRF` is two SHA-256 blocks reduced mod `n`. Walker indices run over
`[0, 2⁶⁴)`; a **work unit** `u` is the index range
`[u·unit_size, (u+1)·unit_size)`. Consequences:

- **No duplication.** Peers holding disjoint index ranges never start the same
  trail, and starting points are uniformly random in the group, which is what
  the rho analysis needs.
- **Resumable.** Progress on a unit is a single integer, the walker cursor.
  Anyone can resume anyone else's unit from the last reported cursor.
- **Auditable.** A claim "walker `i` reached DP `X` after `k` steps" can be
  re-run by anybody in `k ≈ 2^dp_bits` steps.
- **Same walk everywhere.** Because the branch table is derived from the job
  id, a collision between two peers' trails solves the instance exactly as a
  collision on one machine would.

Each walker runs until it hits a DP or a step cap (`20·2^dp_bits` by default,
which catches fruitless cycles under the negation map); a capped walker is
reported as a *dead trail* and costs nothing but its steps.

## 4. Check-ins

The only message in the protocol is the `CheckIn`:

```json
{
  "version": 1,
  "job_id": "…sha256…",
  "peer": "alice.0",            // node.lane; sequence numbers are per peer
  "seq": 17,
  "time": 1757520000,
  "units": [ { "unit": 42, "walkers_done": 128, "steps": 131072,
               "dps": 127, "dead_trails": 1, "completed": false } ],
  "dps": [ { "walker": 10879, "steps": 1031,
             "x": "…", "y": "…", "a": "…", "b": "…" }, … ],
  "solution": null              // hex x once known
}
```

- A **DP record** is self-certifying: the receiver checks the point is on the
  curve, is distinguished, and that `a·P + b·Q = (x, y)`. Two scalar
  multiplications verify work worth `2^dp_bits` group operations, so every
  peer verifies every record it accepts. A forged record is dropped and
  counted; a forged unit report can only make a unit look further along than
  it is, which the lease mechanism below turns into re-work, not corruption.
- A **unit report** is cumulative for `(peer, unit)`; the latest `seq` wins.
- A lane emits a check-in when it claims a unit, every `checkin_every`
  walkers, when the unit completes, and once more with `solution` set when
  its merge produced the answer.

## 5. State as a CRDT

Every peer keeps a `SharedState` that is the merge of all check-ins it has
seen. Each component is a conflict-free replicated data type, so merging is
commutative, associative and idempotent and peers converge regardless of
delivery order or duplication:

| component | CRDT | merge rule |
|---|---|---|
| DP table `key → (a, b, y, walker, peer)` | grow-only map with min-register values | same coefficients: no-op; different: **collision** → solve, keep the coefficient-wise minimum |
| unit claims `unit → peer → report` | per-peer max-register (by `seq`) | later `seq` replaces |
| solution | write-once, verified | accept only if `x·P = Q` |
| check-in log `(peer, seq) → CheckIn` | grow-only set | union |

The log doubles as the gossip payload. A peer's **version vector**
`{peer ↦ max seq}` lets any other peer compute exactly the check-ins it
lacks (`delta_for`).

**Collision solving.** Same point: `(a₁ − a₂)·P = (b₂ − b₁)·Q`, so
`x = (a₁ − a₂)/(b₂ − b₁) mod n`. Under the negation map a key is an
x-coordinate, so the two points may be negatives: then
`(a₁ + a₂)·P = −(b₁ + b₂)·Q`. Both are tried and the candidate is verified
against `Q`. A collision with `b₁ = b₂` is sterile (same trail, e.g. a unit
re-run) and is counted, not solved.

## 6. Claiming and leasing units

There is no assignment. A lane chooses its next unit from its own merged view:

1. If it already holds a **live** claim, continue that unit.
2. Otherwise take the lowest-numbered units that are neither completed nor
   live-leased by another peer; among the first `claim_window` of them pick
   one by hashing the lane id, so lanes whose views lag each other tend to
   spread out.
3. Resume from the highest cursor anyone has reported for that unit.

A claim is **live** while its owner keeps checking in: it expires
`lease_secs` after the last check-in *as received by the local clock*, so
clock skew between peers cannot orphan a unit. When a peer disappears its
unit is picked up from its last cursor by whoever notices first.

Because trails are deterministic, two lanes working the same unit (a race
between lagging views, or a lease that expired while the owner was merely
slow) only waste time; they cannot corrupt the table — the duplicate DPs
arrive with identical coefficients and merge as no-ops. Within one node the
choice and the claim announcement happen under a single lock so its own lanes
never collide.

## 7. Transports

The state and the messages are transport-agnostic. Three transports ship:

**Mailbox** (`mailbox.rs`). A directory:

```
<dir>/job.json
<dir>/checkins/<peer>-<seq>.json    written atomically (tmp + rename)
```

Every peer appends its own check-ins and reads everyone else's on each sync.
Whatever replicates a directory — NFS, Syncthing, Dropbox, `rsync` in cron, a
git repo — is the network. Files are immutable and the merge is idempotent,
so partial syncs are harmless. A node that also gossips over TCP relays what
it learned into the directory (`publish_missing`), so a mailbox can bridge
two TCP islands.

**TCP gossip** (`net.rs`). Plain `std::net`, one JSON object per line. A sync
with a peer is two round trips on one connection:

```
→ pull  {job_id, known: version vector}
← batch {checkins the puller lacks, known: responder's version vector, solution}
→ push  {checkins the responder lacks}
← ack   {accepted, rejected}
```

After one sync the two logs are equal, so any connected peer graph converges
in a few rounds. The topology is the operator's choice: everyone syncing with
one well-known node is the simplest; a ring or a mesh removes the single
point of failure. A node that listens is *not* a coordinator — it holds no
state the others lack, and losing it loses nothing that was gossiped.

**cairn** (`cairn.rs`). A paid network rather than a peer: a
[cairn](https://github.com/aburan28/cairn) node serving a *piecework*
objective whose checker verifies one distinguished point and pays
`unit_price` for each novel accepted one
([design](https://github.com/aburan28/cairn/blob/main/docs/design/rho-piecework.md),
[Stage A](https://github.com/aburan28/cairn/pull/144)). Each DP a lane finds
goes out as cairn's commit–reveal pair over plain HTTP, and the objective's
log comes back as the DP table:

```
POST /submit?kind=commitment   {type, objective_id, submitter, hash, created_at}
        … the epoch turns …
POST /submit?kind=claim        {type, objective_id, submitter, artifact, nonce, created_at, cites: []}
GET  /log                      every accepted claim → a check-in from peer "cairn:<submitter>"
```

The artifact is exactly `{x, y, a, b}` with `2y ≤ p`, so one point has one
spelling whichever walk reached it; a walker index or step count in the
artifact would let a copier re-mint a public point by relabelling it. The
commitment hash and the canonical encoding are cairn's consensus rules,
reproduced here and pinned against its frozen conformance vectors. A record
under a key-shaped submitter is signed with this crate's Ed25519 from the
identity file `cairn identity` writes; a nickname needs no signature.

What is different from the other two transports:

- **Novelty is the artifact, not the point.** A second coefficient pair for
  a point already in the log is a *new* artifact to cairn — it is paid, and
  it is the collision. So the transport deduplicates on the whole artifact
  and never on `x` alone.
- **A reveal waits for the epoch.** A commitment is remembered (and written
  to `<node>.cairn.json`) until the node's epoch turns, then revealed; a
  restart picks the pending ones up. The client has to know the epoch length
  (`--cairn-epoch-secs`, 600 unless the operator set `CAIRN_EPOCH_SECONDS`).
- **Leases are not needed.** cairn pays for the point, not for finishing a
  unit, so an unfinished unit costs nothing and `work_assignment` on the
  cairn side hands out disjoint unit ranges without anyone holding a lease.
  The mailbox/TCP lease machinery still runs locally and is harmless.
- **The negated twin is merged.** Under a walk without the negation map the
  DP table keys on `x:y`; a canonical point from the log and a local
  `(x, −y)` would otherwise never meet, so the transport merges both
  spellings and `solve_collision` handles the opposite-`y` case as before.
- **The answer is claimed too.** With `--answer-objective`, the moment the
  local state solves — from its own points or from the log — `{"k": <64 hex>}`
  is committed to the objective that pays for the discrete log itself, and
  revealed next epoch.

The fake node in `cairn.rs`'s tests validates shape and signatures at the
boundary and refuses a reveal without its commitment, the way `serve.rs` and
`drain` do; the transport was also run against a real `cairn serve --queue`
node on the 50-bit rho objective, with both a signed and a nickname
contributor, and every claim was accepted and paid.

## 8. Failure handling

| event | effect |
|---|---|
| peer crashes mid-unit | lease expires; unit resumed from its last cursor by another lane; DPs it already checked in are kept |
| peer restarts | it re-reads the mailbox / re-syncs, so `next_seq` continues above its own logged maximum and it resumes its own live claims |
| message lost | the next pull fills the gap (version vectors, not "latest only") |
| message duplicated / reordered | idempotent, order-independent merge |
| peer on a different job | rejected by job id |
| forged DP | rejected on verification, counted per node |
| forged progress | at worst a unit is skipped until its lease expires and someone resumes it; the DP table is unaffected |
| network partition | each side keeps working its own units (index ranges are disjoint by construction); the DP tables merge when the partition heals, and any cross-partition collision is found then |

## 9. Cost and tuning

Expected work is `√(πn/2)` group operations (`/√2` with the negation map).
Each DP costs `2^dp_bits` steps on average, so the table holds about
`√(πn/2) / 2^dp_bits` records at the solve, and the check-in bandwidth per
peer is `(steps per second) / 2^dp_bits` records per second, each ~4 scalars.

- `dp_bits`: the default is `¼·log₂n`, i.e. trails of length `n^{1/4}` and a
  table of `n^{1/4}` entries. Raise it to shrink table and traffic; lower it
  to shorten the tail latency after the solving collision happens (the
  collision is only *detected* at the next DP).
- `unit_size`: the granule of claiming. Larger units mean fewer claim
  messages; smaller ones mean less re-work when a lease expires.
- `checkin_every`: how much work is at risk if a lane dies between check-ins.
- `lease_secs`: must exceed the longest gap between a lane's check-ins
  (`checkin_every · 2^dp_bits` steps at the lane's speed) plus sync latency.

Progress is reported as `steps / expected_steps`; passing 100 % means the
median solve time has elapsed — rho's run length is roughly Rayleigh
distributed, so a run at 150 % is unlucky, not broken.

## 10. Trust model, and what is deliberately not done

Participants are *semi-trusted*: they may be lazy or malicious but cannot
damage the shared result, only fail to contribute. This holds because every
fact in the state is verifiable from the job document alone.

Not implemented, and how it would slot in:

- **Signed check-ins / reputation.** Add a per-node key and a signature over
  the canonical check-in; reject unsigned peers or weight leases by past
  validity rate. The `rejected_dps` counter is the input for that.
- **Table sharding.** At `n ≈ 2¹⁰⁰` the DP table no longer fits on one node.
  The CRDT is already keyed by DP; assign key prefixes to nodes and route
  records to the owner of their prefix; collisions are then detected by the
  shard owner. Nothing above changes except who stores what.
- **Log compaction.** The log grows with every check-in. A periodic snapshot
  (DP table + unit views + version vector) would let late joiners skip the
  history.
- **Interval ECDLP (kangaroo).** For `x` known to lie in `[a, a+W)`, the
  same protocol works with tame/wild walkers instead of `a·P + b·Q` starts;
  only `walker_start` and the collision formula change. The GPU kangaroo in
  `gpu/btcpuzzle/` would plug in as a lane whose check-ins carry the same
  record format.
- **Multi-target.** Galbraith–Lin–Scott amortisation over many `Q_i` fits by
  adding a target index to the record and the collision equation.

## 11. Walkthrough

```bash
# 1. Someone writes the job (planting a secret here so the run is checkable).
crypto cryptanalysis rho-collab init --curve demo-40 --secret 1badc0de --out job.json
# 2. Alice listens; Bob and Carol gossip with her; Carol also bridges a directory.
crypto cryptanalysis rho-collab work --job job.json --node alice --threads 4 --listen 0.0.0.0:7000
crypto cryptanalysis rho-collab work --job job.json --node bob   --threads 4 --peer alice:7000
crypto cryptanalysis rho-collab work --job job.json --node carol --threads 2 --peer alice:7000 --mailbox /nfs/collab
# 3. Anyone can look.
crypto cryptanalysis rho-collab status --job job.json --peer alice:7000
crypto cryptanalysis rho-collab status --mailbox /nfs/collab --json
```

On the 40-bit demo curve (`√n ≈ 2²⁰`) three nodes with two lanes each solve
the instance in about five seconds in a release build; every node prints the
same `solution:` line and `verified: true`.

## 12. Tests

`cargo test --lib pollard_collab` covers: job-id stability and field
sensitivity; determinism of derivations; DP verification accepting genuine
and rejecting tampered records; walk invariant `a·P + b·Q = R` under both
walk modes; order-independence and idempotence of the merge; collision
solving in both modes; rejection of foreign jobs and bogus solution claims;
lease expiry and cursor resumption; sequence numbers surviving a reload;
lanes on one node never sharing a unit; two processes' worth of state
converging through a directory; three nodes in a chain converging over TCP
with identical version vectors.
