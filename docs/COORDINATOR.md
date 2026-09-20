# Distributed rho: a coordinator with a URL, agents that dial out

`ca_rho_solve` divides one instance across the threads of one process.
This divides it across machines that cannot reach each other.

Header: [`ca_coord.h`](../include/cryptanalysis/ca_coord.h).
Sources: `src/coord.c` (job, walk, CRDT, wire) and `src/coord_net.c`
(sockets).  Commands: `ca coord-job`, `ca coord`, `ca work`,
`ca coord-status`.  Deployment files: [`deploy/ca-coordinator/`](../deploy/ca-coordinator/).

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
  wins.  A forged one can only make a unit look further along than it
  is, which the lease below turns into re-work, not corruption.
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
behind somebody's load balancer.

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
* **A restarted hub need not be an empty hub.** `ca_coord_hub_params.on_checkin`
  fires for every check-in it accepts; point it at durable storage and
  replay at start.
* **The token is access control, not integrity.** It keeps an
  unauthenticated stranger from flooding the log; every record in the
  log is still self-verifying, so a credentialled liar can still only
  waste their own time.  It is compared in constant time and carried by
  plain HTTP, so TLS belongs in a terminator in front — an `https://`
  URL is refused rather than silently downgraded.

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
| forged progress | at worst a unit is skipped until its lease expires; the DP table is unaffected |
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

# 2. On the reachable host: the hub.
ca coord --job job.txt --listen 127.0.0.1:8080 --token-file /etc/ca/token \
    --require-token

# 3. On every agent, anywhere.  The URL is the whole configuration.
export CA_COORDINATOR_URL=https://rho.example.com
export CA_COORDINATOR_TOKEN=…
ca work --node "$(hostname)" --threads "$(nproc)"

# 4. From anywhere with the token.
ca coord-status
```

Step 3 takes no `--job`, no listening port and no peer list: the agent
fetches the job from the hub, so a fleet image is baked once and aimed
with an environment variable.

On the 51-bit subgroup above, three such agents with two lanes each
solve the instance in a couple of seconds on one machine; the hub
reports `pushed` in the hundreds and each agent reports `received` in
the dozens, which is the reverse channel carrying other agents' points
to processes that never listened on anything.

## 12. Tests

`ctest -R coord` (506 checks) covers: job encode/decode and the id's
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
