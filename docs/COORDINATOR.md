# Distributed rho: a coordinator with a URL, agents that dial out

`ca_rho_solve` divides one instance across the threads of one process.
This divides it across machines that cannot reach each other.

**Where each piece lives.**  The parts that decide what is *true* are in
C, in one implementation, because an agent and a coordinator that
disagree about whether a point is genuine have no shared table at all:
`include/cryptanalysis/ca_coord.h` with `src/coord.c` (job, walk, CRDT,
wire) and `src/coord_net.c` (the agent's side of the connection).

The coordinator itself is a **network service** -- it has to be
deployed, fronted by a load balancer, scaled to zero and restarted by a
scheduler -- so it is written in Go and reuses all of the above through
cgo: [`bindings/go/cmd/ca-coordinator`](../bindings/go/cmd/ca-coordinator),
with a Helm chart in [`deploy/helm/ca-coordinator`](../deploy/helm/ca-coordinator)
and images from [`deploy/docker/Dockerfile`](../deploy/docker/Dockerfile).
It reimplements none of the cryptography: it parses the job, verifies
points and merges check-ins by calling this library.

Commands: `ca coord-job` (mint a job), `ca work` (an agent),
`ca coord-status` (look), `ca-coordinator` (the service).

## 1. The shape the deployment actually has

Parallel rho normally assumes the workers can talk to each other.  On a
cloud fleet almost none of them can: they sit in private subnets, behind
NAT, on spot instances, in containers with no inbound rule.  What *is*
reachable from everywhere is one host — an instance with an elastic IP,
or a load balancer in front of one.  So the topology that deploys is a
hub, and every connection has to be opened by the agent:

```
  agent (private subnet)  ────┐
  agent (spot fleet)      ────┼──►  https://rho.example.com   (EC2 + nginx)
  agent (laptop, NAT)     ────┘         GET /v1/channel
                                        Upgrade: ca-rho/1
                                   ◄─── the hub pushes back down
                                        the socket the agent opened
```

The reverse arrow is the point.  Once an agent has dialled in, the hub
uses that same socket in the other direction to push other agents'
distinguished points and the solution to a machine it could never have
dialled.  Nothing polls.

## 2. Why dividing by start point, not by search space

Giving each machine its own walk function does not divide rho at all:
collisions only count *within* a walk function, so `m` machines give no
speed-up.  Van Oorschot–Wiener's fix is that everyone walks the **same**
function and reports only distinguished points (points whose hash has
`dp_bits` trailing zeros), so two trails that meet anywhere stay merged
and arrive at the same DP — and a table of everyone's DPs detects a
collision between any two machines.  The parallel speed-up is then
linear in the number of machines.

What can be partitioned is the set of **trail start points**.  From the
job id every participant derives, offline and identically:

| derived | formula |
|---|---|
| branch `i` of the `r`-adding walk | `M_i = α_i·G + β_i·H`, `(α_i, β_i) = PRF(id, "branch", i)` |
| start of **walker `k`** | `R_k = a_k·G + b_k·H`, `(a_k, b_k) = PRF(id, "walker", k)` |

A **work unit** is a contiguous range of walker indices, `unit_size`
wide.  So "dividing the search space" is just agreeing on integers:

* **No duplication.** Agents holding disjoint ranges never start the
  same trail, and the starts are uniform in the group, which is what the
  rho analysis needs.
* **Resumable.** Progress on a unit is one integer, the walker cursor.
  Anyone can resume anyone else's unit from the last reported cursor.
* **Auditable.** "walker `k` reached DP `X` after `s` steps" can be
  re-run by anybody in `s ≈ 2^dp_bits` steps.

The PRF is splitmix64 over `(id, tag, index)`.  It is not a
cryptographic PRF and is not asked to be one: its job is to make the
derived values look random and, much more importantly, to make them
*identical* everywhere.  An agent that biases its own start points only
wastes its own time, because the coefficients travel with the point and
are checked.

## 3. The check-in

One line, the only message in the protocol:

```
ci <job-id> <peer> <seq> <time> U:unit,walkers,steps,dps,dead,done;… D:walker,steps,x0,x1,x2,x3,a,b;… S:<x|->
```

* A **DP record is self-certifying**: the receiver checks the point is a
  valid element, really is distinguished, and that `a·G + b·H` equals
  it.  Two scalar multiplications verify work worth `2^dp_bits` steps,
  so every receiver verifies every record it accepts.  A forged record
  is dropped and counted.
* A **unit report** is cumulative for `(peer, unit)`; the later `seq`
  wins.  Unlike a distinguished point, it is *not* self-verifying, and
  it is worth being exact about what that costs.  A claim in progress is
  held only by its lease, so a forged one frees itself again after
  `lease_secs`.  A `completed` flag is not leased: it retires the unit
  for good, and a peer holding the token can therefore retire units it
  never walked.
  What that costs is parallelism, not the answer.  A unit is a range of
  *start points*, and the solution comes from a collision between any
  two trails; skipping a range means those particular starts are never
  walked, not that the collision is missed or that a wrong answer can be
  reached.  The DP table -- where correctness actually lives -- is
  untouched, because every record in it is verified individually.
  Making completion expire too would close this, and break the thing it
  is for: every finished unit would come back around and lanes would
  re-walk the low units forever instead of advancing.
* A lane checks in when it claims a unit, every `checkin_every` walkers,
  when the unit completes, and once more with `S:` set when its merge
  produced the answer.

The format is deliberately not JSON.  It is the library's only parser
that faces the network, so it is flat, fixed and separator-delimited —
small enough to read in one sitting — and `fuzz/fuzz_coord.c` runs it
against arbitrary bytes, asserting that whatever decodes re-encodes
identically and that no input can produce a solution failing `x·G == H`.
Peer names are restricted to printable ASCII without the separators, on
both encode and decode, so a name can never inject a field.

## 4. The state is a CRDT

Every participant — agent and hub alike — keeps the merge of all the
check-ins it has seen.  Each component is conflict-free, so merging is
commutative, associative and idempotent and everyone converges whatever
order anything arrives in, however often:

| component | merge rule |
|---|---|
| DP table, keyed by the canonical point | grow-only; same key with *different* coefficients **is** the collision → solve; identical coefficients are the same trail and merge as a no-op |
| unit reports | per-peer max-register by `seq` |
| solution | write-once, and only if `x·G == H` |
| the log, keyed by `(peer, seq)` | union |

The log doubles as the transport payload, and it is stored in its wire
form: one line is exactly what a delta has to send.  A **version vector**
`{peer ↦ max seq}` lets any participant compute exactly what another
lacks (`ca_coord_delta_for`), which is why one round trip makes two logs
equal.

**Solving.** Same point, two coefficient pairs: `(a₁ − a₂)·G = (b₂ − b₁)·H`,
so `x = (a₁ − a₂)/(b₂ − b₁) mod n`.  Under the negation map the two
points may be negatives, giving `(a₁ + a₂)·G = −(b₁ + b₂)·H`; both are
tried and the candidate is verified against `H`.  A collision with
`b₁ = b₂` is sterile (the same trail, e.g. a re-run unit) and is
counted, not solved.

## 5. Claiming, not assigning

There is no assignment.  A lane picks from its own merged view: the
lowest-numbered units that are neither completed nor live-leased by
somebody else, and among the first `claim_window` of those, the one its
own name hashes to — so lanes whose views lag each other spread out
instead of piling onto the same unit.

A claim is **live** while its owner keeps checking in.  It expires
`lease_secs` after the last check-in *as received by the local clock*,
so a peer's skewed clock cannot orphan a unit.  When an agent
disappears, its unit is picked up from its last cursor by whoever
notices first.

Two lanes on one unit is only waste, never corruption: trails are
deterministic, so the duplicate DPs arrive with identical coefficients
and merge as no-ops.

## 6. The transport

HTTP/1.1, because what is reachable from everywhere is a URL on port 443
behind somebody's load balancer.  It is `net/http` on the serving side:
the routes below are ordinary handlers, and the channel is a hijacked
connection after the upgrade.

| route | method | purpose |
|---|---|---|
| `/healthz` | GET | load-balancer probe; outside the token, and says nothing about the job |
| `/v1/job` | GET | the job document, so an agent needs only a URL |
| `/v1/status` | GET | progress and hub counters, as JSON |
| `/v1/sync` | POST | one-shot pull+push, for `coord-status` and anything that cannot hold a socket open |
| `/v1/channel` | GET + `Upgrade: ca-rho/1` | the reverse channel |

The channel handshake is an ordinary HTTP upgrade answered with `101
Switching Protocols` — the WebSocket move, which is exactly what proxies
already know how to pass through.  After it, both directions speak one
line per message:

```
agent → hub   hello <job-id> <peer> <peer>:<seq> …    who I am, what I have
hub   → agent ci …                                    what I lack — and later, unprompted
agent → hub   ci …                                    what I found
hub   → agent ack <accepted> <rejected>
either        ping                                    keepalive through idle timeouts
```

## 7. What the hub is, and is not

It is a **rendezvous, not an authority**.  It holds the same CRDT every
agent holds, verifies every point on arrival with the same two scalar
multiplications, and hands out no work.  Therefore:

* **Losing it loses no work.** Agents keep walking their claimed units
  and keep their own DP tables; when it returns they reconverge, exactly
  as after a network partition.  It is a single point of *reachability*,
  not of truth.
* **A restarted hub need not be an empty hub.** `-log FILE` appends every
  accepted check-in and replays the file at start.  The wire form is the
  storage form, so the file is greppable text, and replay is safe at any
  time because the merge is idempotent.  In the chart this is
  `coordinator.persistence.enabled`.
* **The token is access control, not integrity.** It keeps an
  unauthenticated stranger from flooding the log; every record in the
  log is still self-verifying, so a credentialled liar can still only
  waste their own time.  It is compared in constant time and carried by
  plain HTTP, so TLS belongs in a terminator in front — an `https://`
  URL is refused rather than silently downgraded.

## 7a. More than one hub: federation

A campaign that spans clusters does not want one hub in one of them.  It
wants a hub in each, and they have to agree.

**This needs no new protocol, and no leader.**  `/v1/sync` is already a
symmetric anti-entropy exchange — post what you hold and a version vector
describing it, receive what you lack — so a hub federates by being a
client of the endpoint it already serves.  Each peer is synced on its own
goroutine, on a timer:

```
  eu-west-1  ◄────── /v1/sync ──────►  us-east-1
      ▲                                    ▲
      │ agents dial their own              │
      │ regional hub, as before            │
```

What makes this safe rather than merely convenient is the merge.  It is
commutative, associative and idempotent, and every record carries its own
proof, checked on arrival by whoever receives it.  So:

* **Any shape works.** A pair, a ring, a full mesh, a hub-and-spoke.
  There is no order the exchanges must happen in and no partition that
  needs healing in a particular direction.
* **There is nothing to elect.** No leader, no quorum, no split brain —
  because no hub is ever the authority about anything.
* **A peer cannot lie you into a wrong answer.** Records from a peer go
  through `absorb`, the same path an agent's check-in takes: a foreign
  job, a forged point or a bogus solution is refused identically.
  Peering grants a hub no authority it did not already have; a broken or
  hostile peer costs bandwidth.
* **An unreachable peer is not an outage.** It is counted
  (`carho_peer_errors_total`, labelled by peer) and retried; the hub and
  its own agents carry on.  Every exchange is bounded by
  `-peer-timeout` (`federation.timeout`), because the failure that
  matters is not a peer that is *down* — that one errors immediately —
  but a peer that accepts the connection and then never answers.
  Unbounded, that one holds its loop forever: never retried, never
  counted, and so invisible to whoever is watching the fleet.

The first exchange with a peer sends only a version vector, no check-ins.
We have no idea what it holds, and the alternative — assuming it holds
nothing — would dump the whole log at it after every restart.  Its reply
says where it stands, and from then on each round sends exactly the
difference.

Configure it with `-peer name=url` (repeatable) or, in the chart:

```yaml
federation:
  peers:
    - name: eu-west-1
      url: http://rho.eu-west-1.internal:8080
    - name: us-east-1
      url: https://rho.us-east-1.example.com
  interval: 5s
```

Two things the chart refuses at template time rather than at 3 a.m.: a
peer with no URL, and peers configured alongside `networkPolicy.enabled`
with no `extraIngressFrom` — a peer hub is not an agent pod, so the
policy would refuse it and the federation would look configured while
exchanging nothing.

`replicaCount` is still one **per release**, and the message now says
why: the replicas of a Deployment do not gossip with each other, so a
second would keep its own half of the table.  More than one hub means a
release per cluster, listed in each other's `federation.peers`.

**What this does not do is raise the memory ceiling.** Every hub still
ends up holding every point, so federation buys reachability, locality
and survival — not capacity.  Capacity is what the distinguished-point
backend below is for.

## 7b. Where distinguished points are remembered

The DP table is the one part of the state whose size is set by the
campaign rather than by the code.  It is an open-addressed hash table of
roughly 80 bytes an entry, so a hub holds order 10⁸ points comfortably
and 10¹⁰ not at all.

So it sits behind `ca_coord_dp_store` (in `ca_coord.h`): `put` a record,
and learn whether it was fresh, a duplicate trail, or a collision — with
the stored coefficients handed back.  The in-process table is now just
the default implementation of that interface.

Two rules a backend must honour, because correctness rests on them:

* **Identity is the point, never the key.** `key` is a hash, offered as a
  bucketing and routing hint.  Two records are the same point when their
  `point` words are equal and not otherwise.  Those words come from
  `ca_group_decode`, which is canonical for every group here, so a
  backend can compare them byte for byte while knowing nothing about the
  group.  This is also what makes sharding by `key` safe: **a collision
  is two equal points, so both copies hash alike and land on the same
  shard.**  Partitioning cannot hide a collision.
* **Never decide what is true.** A backend remembers points and reports
  what it held.  It does not verify, and it does not solve — callers
  verify before offering a record, and the coefficients that come back
  are solved by the library.  A backend that lies can waste work and
  cannot forge an answer.

A backend that cannot store is counted (`rejected_dps`) and is not fatal.

## 8. Failure handling

| event | effect |
|---|---|
| agent crashes mid-unit | the lease expires; the unit is resumed from its last cursor by another lane; DPs it already checked in are kept |
| agent loses the channel | it keeps walking and queues check-ins; they go up when the channel returns, and `ca_coord_agent_flush` drains the queue before the process exits |
| hub restarts or is replaced | agents reconnect with exponential backoff (1 s → 30 s) and re-push; with a durability hook the hub reloads its log, otherwise it refills from the agents' next pushes |
| message lost | the next pull fills the gap — version vectors, not "latest only" |
| message duplicated or reordered | idempotent, order-independent merge |
| agent on a different job | refused by job id |
| forged DP | refused on verification, counted per state |
| forged progress (in flight) | the claim frees itself after `lease_secs` |
| forged progress (`completed`) | that unit's start points are never walked; costs parallelism, not the answer, and the DP table is unaffected |
| network partition | each side keeps working its own units (index ranges are disjoint by construction); the tables merge when it heals, and any cross-partition collision is found then |

## 9. Cost and tuning

Expected work is `sqrt(pi n / 2)` group operations (`/sqrt 2` with the
negation map).  Each DP costs `2^dp_bits` steps on average, so the table
holds about `sqrt(pi n / 2) / 2^dp_bits` records at the solve, and a
peer's check-in bandwidth is `(steps per second) / 2^dp_bits` records
per second, each about 8 integers.

* `dp_bits` — default `¼·log₂ n`.  Raise it to shrink the table and the
  traffic; lower it to shorten the tail after the solving collision
  happens (a collision is only *detected* at the next DP).
* `unit_size` — the granule of claiming.  Larger means fewer claim
  messages; smaller means less re-work when a lease expires.
* `checkin_every` — how much work is at risk if a lane dies between
  check-ins.
* `lease_secs` — must exceed the longest gap between a lane's check-ins
  plus sync latency.

Progress is reported as `steps / expected_steps`; passing 100 % means the
median solve time has elapsed.  Rho's run length is roughly Rayleigh
distributed, so a run at 150 % is unlucky, not broken.

## 10. Trust model, and what is deliberately not done

Participants are *semi-trusted*: they may be lazy or malicious but
cannot damage the shared result, only fail to contribute.  This holds
because every fact in the state is verifiable from the job document
alone.

Not implemented, and how it would slot in:

* **Signed check-ins and reputation.** Add a per-agent key and a
  signature over the canonical line; reject unsigned peers or weight
  leases by past validity rate.  The rejected-DP counter is the input.
* **Table sharding.** The CRDT is keyed by DP, so assigning key prefixes
  to hubs and routing records to the owner of their prefix changes
  nothing above except who stores what.  This is what a table too large
  for one host needs — not a bigger instance.
* **Log compaction.** The log grows with every check-in; a periodic
  snapshot (DP table, unit views, version vector) would let late joiners
  skip the history.
* **Interval rho (kangaroo).** The same protocol works with tame/wild
  walkers; only the start derivation and the collision equation change.
* **A 64-bit job id is an agreement check.** It tells two agents they
  are walking the same thing; nothing rests on preimage resistance, and
  a wrong id is refused anyway.

## 11. Walkthrough

```sh
# 1. Anywhere: write the job document everyone shares.
ca coord-job --group zp --p 4503599627372423 --order 2251799813686211 \
    --g 1456600859624672 --h 4047005209878851 --dp-bits 16 --unit-size 64 \
    --seed 21 --out job.txt

# 2. On the reachable host: the coordinator (a Go binary; build it with
#    `go build ./cmd/ca-coordinator` from bindings/go).
ca-coordinator -job job.txt -listen :8080 -token-file /etc/ca/token \
    -require-token -log /var/lib/ca/checkins.log

# 3. On every agent, anywhere.  The URL is the whole configuration.
export CA_COORDINATOR_URL=https://rho.example.com
export CA_COORDINATOR_TOKEN=…
ca work --node "$(hostname)" --threads "$(nproc)"

# 4. From anywhere with the token.
ca coord-status
```

On Kubernetes that is one `helm install`; see
[`deploy/helm/ca-coordinator`](../deploy/helm/ca-coordinator).

Step 3 takes no `--job`, no listening port and no peer list: the agent
fetches the job from the hub, so a fleet image is baked once and aimed
with an environment variable.

On the 51-bit subgroup above, three such agents with two lanes each
solve the instance in a couple of seconds on one machine; the hub
reports `pushed` in the hundreds and each agent reports `received` in
the dozens, which is the reverse channel carrying other agents' points
to processes that never listened on anything.

## 12. Tests

`ctest -R coord` (464 checks) covers: job encode/decode and the id's
sensitivity to every field that changes the walk; refusal of an altered
document; determinism of the derivations across two contexts, and the
`a·G + b·H = R` invariant; DP verification accepting genuine records and
rejecting tampered ones in both walk modes; trail reproducibility;
wire round-trips, including a dozen malformed lines and a peer name
carrying a separator; order-independence and idempotence of the merge;
refusal of a foreign job, a forged point and a bogus solution claim;
lease expiry and cursor resumption; sequence numbers continuing above
the log; delta/version-vector agreement; two lanes merging to a
solution; URL parsing including the refused `https://`; the one-shot
sync path; and — the property the module exists for — two agents that
never listen on anything converging through a hub they dialled out to,
with the solution reaching the agent that did not find it.

`fuzz/fuzz_coord.c` fuzzes the two decoders and the merge.
