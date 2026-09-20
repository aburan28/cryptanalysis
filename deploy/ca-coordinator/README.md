# Running the distributed rho from one coordinator on a VM

**On Kubernetes, use [`deploy/helm/ca-coordinator`](../helm/ca-coordinator)
instead** -- it is the same two processes with the topology written down.
This directory is the plain-VM (EC2) version.

**This directory makes no performance claim.** It is plumbing: no row in
[`docs/BENCHMARKS.md`](../../docs/BENCHMARKS.md) moves because of it.
What it is allowed to claim is the failure mode it removes, and that is
exactly one — *the fleet could not reach each other*.

Parallel rho normally assumes the workers can accept connections. On a
cloud fleet almost none can: private subnets, NAT, spot instances,
containers with no inbound rule. One host can be reached by everybody —
an instance with an elastic IP, or a load balancer. So the topology that
deploys is a hub, and the connections are opened by the agents:

```
  agent (private subnet)  ────┐
  agent (spot fleet)      ────┼──►  https://rho.example.com   (EC2 + nginx)
  agent (laptop, NAT)     ────┘         GET /v1/channel
                                        Upgrade: ca-rho/1
                                   ◄─── the hub pushes back down
                                        the socket the agent opened
```

That last arrow is the point: once an agent has dialled in, the hub uses
the same socket in the other direction — the **reverse channel** — to
push other agents' distinguished points and the solution to a machine it
could never have dialled.

The protocol, the CRDT and the trust model are in
[`docs/COORDINATOR.md`](../../docs/COORDINATOR.md). This file is how to
run it.

## The four commands

```sh
# 1. Anywhere: the job document everyone shares.
ca coord-job --group zp --p P --order N --g G --h H \
    --dp-bits 16 --unit-size 64 --seed 21 --out job.txt

# 2. On the EC2 instance: the hub (a Go binary; bind loopback, TLS in front).
ca-coordinator -job job.txt -listen 127.0.0.1:8080 \
    -token-file /etc/ca/token -require-token -log /var/lib/ca/checkins.log

# 3. On every agent, anywhere: one URL is the whole configuration.
export CA_COORDINATOR_URL=https://rho.example.com
export CA_COORDINATOR_TOKEN=…
ca work --node "$(hostname)" --threads "$(nproc)"

# 4. From anywhere with the token.
ca coord-status
```

Step 3 takes no `--job`, no listening port and no peer list: the agent
fetches the job document from the hub, so a fleet image is baked once
and aimed with an environment variable. `--coordinator` and `--token`
are flags too; the environment variables exist so that a systemd unit
and an autoscaling group can carry them instead.

## Files here

| file | what it is |
|---|---|
| `ca-coordinator.service` | the hub unit (the Go binary): loopback bind, token file, `Restart=always`, hardened |
| `ca-agent.service` | the agent unit: environment file, no inbound anything |
| `nginx.conf` | TLS in front, **with the upgrade headers the reverse channel needs** |
| `user-data.sh` | EC2 user-data: build, job from S3, token from Secrets Manager, start the unit |

## Wiring it up on AWS

**Security groups.** The hub instance needs inbound 443 from the agents
(or from the ALB's group) and nothing else. Agents need **no inbound
rule at all** — that is the whole reason for the reverse channel — and
outbound 443 to the hub.

**TLS.** The coordinator speaks plain HTTP on purpose: it is one
process, and a TLS stack inside it is a maintenance surface with no
upside when every deployment already has a terminator. Put nginx (see
`nginx.conf`) or an ALB in front and bind the hub to `127.0.0.1`. The
client refuses an `https://` URL rather than silently downgrading it, so
agents given one must reach it through that terminator.

**Load balancers and proxies.** Two settings decide whether the reverse
channel works at all:

* the proxy must pass `Upgrade` and `Connection` through (`nginx.conf`
  does; an ALB does this for WebSocket-style upgrades natively);
* the idle timeout must exceed the hub's keepalive. The hub pings an
  idle channel every `idle_secs / 3` — 100 s at the default — so an ALB
  idle timeout of 300 s or more is safe. Below that, channels are closed
  under the agents, which costs a reconnect (with backoff) and nothing
  else, but fills the logs.

`/healthz` is deliberately outside the token so a target group can poll
it; it reveals nothing about the job.

**The token.** Generate it with `openssl rand -hex 32`, keep it in
Secrets Manager, and hand it to processes as a file (`--token-file`) or
an environment variable — never as a command-line argument, which `ps`
shows to every local user. `--require-token` makes the hub refuse to
start without one; set it whenever the bind address is reachable from
outside the host. A hub on a public address with no token warns loudly
and keeps going, because a private-subnet hub behind a security group is
a legitimate configuration.

**Durability.** The hub's state is in memory, and an EC2 instance is
replaceable by design. Losing the hub costs no work — agents keep
walking and reconverge when it returns — but it does cost the hub's view
of the DP table until they re-push. `-log FILE` appends every accepted
check-in and replays the file at start, so a replacement starts where
the last one stopped; the merge is idempotent, so replay is always safe
and the file is ordinary greppable text.

**Instance sizing.** The hub does two scalar multiplications per
distinguished point it accepts and holds the DP table in memory: at the
default `dp_bits` the table is about `n^{1/4}` records of eight integers,
so a 2-vCPU instance carries a fleet whose aggregate rate is a few
thousand DPs a second. When the table stops fitting, the answer is the
sharding sketched in §10 of the design doc, not a bigger instance.

**Spot agents.** An interrupted agent costs the unfinished part of its
current unit: the lease expires after `lease_secs` and another agent
resumes the unit from the last cursor anybody reported. Nothing else is
needed to make the fleet spot-safe.

## Checking it end to end, on one machine

```sh
ca gen --group zp --p 4503599627372423 --order 2251799813686211 \
    --x 777777777777777 --seed 3
ca coord-job --group zp --p 4503599627372423 --order 2251799813686211 \
    --g 1456600859624672 --h 4047005209878851 \
    --dp-bits 16 --unit-size 64 --seed 21 --out job.txt

echo "$(openssl rand -hex 16)" > token
ca-coordinator -job job.txt -listen 127.0.0.1:8080 -token-file token &

export CA_COORDINATOR_URL=http://127.0.0.1:8080 CA_COORDINATOR_TOKEN="$(cat token)"
for n in alice bob carol; do ca work --node $n --threads 2 & done
wait
```

Every agent and the hub print the same `"x":777777777777777`, no agent
ever listened on a port, and the hub's `"pushed"` and each agent's
`"received"` are non-zero — that is other agents' points arriving over a
socket the agent opened.
