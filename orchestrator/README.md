# The orchestration layer: a control plane and agents

`ca` solves a discrete logarithm in one process. This directory is what turns
that into a fleet: a **control plane** that owns a campaign and its corpus,
and **agents** that lease work units and walk them — as Kubernetes pods, as
systemd services on EC2 instances, or as processes on a laptop.

```
                      ┌──────────────────────────────────────────┐
   lease ─────────────▶│  ca-control                              │
   points ────────────▶│    campaigns · units · leases (fenced)   │
   heartbeat ─────────▶│    corpus (verified) · merger · solution │
                      │    /v1 · /metrics · /healthz · /readyz   │
                      └────────────────┬─────────────────────────┘
                                       │ state dir: campaigns/, units.jsonl, corpus/
   ┌───────────┐  ┌───────────┐  ┌─────┴─────┐
   │ ca-agent  │  │ ca-agent  │  │ ca-agent  │   each runs `ca dist-walk`
   │  (pod)    │  │ (systemd) │  │  (spot)   │   as a subprocess
   └───────────┘  └───────────┘  └───────────┘
```

## Why this is distributed and not just parallel

Running `ca solve` on N machines with N different seeds is N independent
searches. Each expects to do the full `1.25·√n` steps; the fleet's *chance*
of an early answer improves, but its total work is N times one machine's.

The van Oorschot–Wiener parallel collision search distributes properly, and
the reason is a single rule: **every walker iterates the same function** and
reports only its *distinguished points*. Two walks that ever meet stay
together and reach the same distinguished point, whichever machines they ran
on, so P machines finish in expected `1/P` of the time for the *same* total
work. The library implements that rule in
[`ca_dist.h`](../include/cryptanalysis/ca_dist.h) and this layer is what
makes it a fleet.

Everything else here follows from three properties of that work:

| property | what it buys |
|---|---|
| A unit is **replayable** — its points are a pure function of `(campaign seed, unit id)` | an expired lease can simply be re-issued; at-least-once delivery needs no dedupe protocol |
| A unit is **disposable** — the search is a random walk, not a partition | a killed agent is not an incident; spot capacity is the right place to run |
| A point is **verifiable** — `Y = a·G + b·H` and really distinguished | the server can accept points from agents it does not trust |

## The three invariants

**The server trusts no agent.** Every point is checked before it enters the
corpus: the coordinates must be a group element, the point must really be
distinguished under the campaign's cutoff, and the exponents must really
produce it. That costs two scalar multiplications against the `2^dpBits` walk
steps that produced the point. Every answer is checked too: a collision gives
a *candidate* `x`, and `x·G == H` is verified before it is reported. A buggy
agent, a hostile one, or a 64-bit hash collision costs a rejected point —
never a wrong answer.

**Every write is fenced.** Each lease gets a monotonically increasing fence.
An agent that was paused past its lease expiry — a stop-the-world GC, a
frozen VM, a partition that healed — wakes up believing it owns a unit that
somebody else now holds, and every write it attempts is rejected because the
fence is stale. No lease length can prevent that; only a fence can. The agent
finds out on its next heartbeat and stops walking, because further steps
would produce points the server will refuse.

**A campaign is immutable.** Its seed, multiplier count and cutoff define the
walk function, and a fleet that disagrees about any of them produces corpora
that can never collide — silently. Those fields are hashed into a
`Fingerprint`, agents echo it on every upload, and a mismatch is refused with
`412` rather than stored. The control plane is the only thing allowed to
choose a seed, and it draws it from the OS CSPRNG: two campaigns that share a
seed merge into each other and solve neither instance.

## Running it

Build both halves:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j
cd orchestrator && go build -o ../build/ca-control ./cmd/ca-control \
                && go build -o ../build/ca-agent   ./cmd/ca-agent
```

The whole thing on one machine, with a real answer at the end:

```sh
orchestrator/scripts/smoke.sh
```

By hand:

```sh
# 1. an instance whose answer you keep to yourself
./build/ca gen --group zp --p 2000000579 --order 1000000289 --seed 42

# 2. the control plane
CA_TOKEN=secret ./build/ca-control serve --listen :8080 --state /var/lib/ca-control

# 3. the campaign (once; a campaign is immutable)
CA_TOKEN=secret ./build/ca-control create --server http://localhost:8080 \
    --name demo --group zp --p 2000000579 --order 1000000289 \
    --g <base> --h <target>

# 4. as many agents as you have cores, anywhere that can reach the server
CA_TOKEN=secret ./build/ca-agent --server http://localhost:8080 --ca ./build/ca

# 5. watch
CA_TOKEN=secret ./build/ca-control status --server http://localhost:8080 --watch 5s
```

## Deploying it

**Kubernetes** — [`deploy/k8s`](deploy/k8s), `kubectl apply -k deploy/k8s`.
The control plane is a single-replica StatefulSet with a volume; the agents
are a Deployment you scale with `kubectl scale`. The manifests explain the
choices inline, including why the control plane is *not* replicated (the
corpus and the lease table are in one process; making it horizontal means
moving the corpus into a shared store, which is a different design) and why
the campaign is created by a one-shot Job rather than a field in a spec.

**EC2 with systemd** — [`deploy/systemd`](deploy/systemd), `./install.sh both 8`.
One templated unit per core (`ca-agent@0…7`), a hardened service file, and
[`ec2-user-data.sh`](deploy/systemd/ec2-user-data.sh), which also installs a
spot-interruption watcher: the two-minute notice becomes a SIGTERM, so the
agent uploads the points it has and hands its unit back instead of losing
both.

**Container** — [`deploy/docker/Dockerfile`](deploy/docker/Dockerfile) builds
the C library, runs part of its test suite, builds both Go binaries and ships
all three in a non-root image with a read-only root filesystem.

## The API

`POST` unless noted. Everything is JSON except the point upload, which is a
raw array of 32-byte records — base64 in an envelope would cost a third more
bytes on the fleet's only high-volume path.

| endpoint | what it does |
|---|---|
| `/v1/agents/register` | announce an agent; returns the heartbeat interval |
| `/v1/agents/heartbeat` | renew a lease and learn whether it is still yours (`lost`, `drain`) |
| `/v1/units/lease` | take a unit; `empty` with a retry hint is a normal answer |
| `/v1/units/points` | upload records; returns accepted/duplicate/rejected and the solution if this was it |
| `/v1/units/complete` | finish or fail a unit |
| `/v1/campaigns` | `GET` list, `POST` create |
| `/v1/status` | one object for the CLI, a dashboard and the alarms |
| `/metrics` | Prometheus text format |
| `/healthz`, `/readyz` | liveness (no auth) and readiness (fails while draining) |

`409 Conflict` means the lease was lost and the agent must stop — it is not
retryable. `412` means the fingerprint does not match.

## Testing

```sh
cd orchestrator && go test ./...          # needs ../build/ca, or set CA_BIN
```

Three layers, and the middle one is the interesting one:

- **Unit tests** for leases, fences, verification, restart recovery, auth,
  draining and metrics.
- **Cross-checks against the C library** (`internal/dlog`): this package
  re-implements the element hash, the record format and the collision solve
  in Go, and the tests require it to agree with `ca` exactly — every point
  the C walker produces must verify here, and both mergers must reach the
  same discrete logarithm. Two independent implementations agreeing on a
  number neither was told is a much stronger check than either against
  itself. (The Go side has to reproduce the library's *Montgomery* form
  inside the hash; get that wrong and every honest point looks
  undistinguished, which in production is a fleet doing perfect work that the
  server throws away.)
- **End to end** (`internal/agent`): four agents, each running the real `ca`
  binary in a real subprocess against one control plane, solving an instance
  with a unit budget far below the expected work of one search — so the
  answer can only have come from merged corpus.

## What is deliberately not here

- **A replicated control plane.** See above; it is a real design and it needs
  a shared corpus store, not a second replica.
- **Autoscaling.** The signal that matters is binary — the campaign has work
  until it is solved — so a CPU-based HPA would only observe that the agents
  are busy, which they are by construction. A KEDA `ScaledObject` on
  `ca_campaign_units_pending` is the honest version when a cluster already
  runs KEDA.
- **The negation map.** The library's single-process solver uses it for its
  `√2`; the distributed walk does not, because escaping the fruitless cycles
  it causes needs per-walk state that must agree bit for bit on every
  machine, and a distributed walk that disagrees with itself does not fail
  loudly — it quietly stops finding collisions.
- **Any performance claim.** This layer schedules work; it does not make the
  walk faster. The measured constants are the library's, in
  [`docs/BENCHMARKS.md`](../docs/BENCHMARKS.md).
