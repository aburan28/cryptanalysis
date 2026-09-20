# ca-coordinator

One coordinator, many agents that dial out to it, on Kubernetes.

```
  agent pod  ────┐
  agent pod  ────┼──►  Service :8080  ──►  coordinator pod
  agent pod  ────┘         GET /v1/channel
                           Upgrade: ca-rho/1
                      ◄─── pushed back down the same socket
```

The agents open every connection; nothing ever connects *to* an agent.
That is why they can sit on spot capacity, in a namespace with no
inbound traffic allowed at all (`networkPolicy.enabled=true` writes that
down), or outside the cluster entirely behind NAT.

The protocol, the CRDT and the trust model are in
[`docs/COORDINATOR.md`](../../../docs/COORDINATOR.md). This file is how
to run it.

## Install

```sh
# 1. Mint the job document (once, anywhere).
ca coord-job --group zp --p 4503599627372423 --order 2251799813686211 \
    --g 1456600859624672 --h 4047005209878851 \
    --dp-bits 16 --unit-size 64 --seed 21 --out job.txt

# 2. Install.  --set-file, not --set: the job line contains commas and
#    '=', which --set parses as structure.
helm install rho deploy/helm/ca-coordinator \
    --set-file job.document=job.txt \
    --set auth.token="$(openssl rand -hex 32)" \
    --set agents.replicaCount=10
```

Agents need nothing else: the chart points them at the Service, and they
fetch the job document from it.

Bring your own Secret and ConfigMap instead, which is what you want if
the token is managed by External Secrets or SOPS:

```sh
kubectl create configmap rho-job --from-file=job.txt
kubectl create secret generic rho-token --from-literal=token="$(openssl rand -hex 32)"
helm install rho deploy/helm/ca-coordinator \
    --set job.existingConfigMap=rho-job --set auth.existingSecret=rho-token
```

## What the chart refuses to do

Three configurations fail at template time rather than at 3 a.m.:

* **no job document** — there is nothing to coordinate;
* **`coordinator.replicaCount` other than 1** — the coordinator holds the
  shared distinguished-point table in memory, so two replicas would each
  hold half of it and miss every collision that spans them, which is the
  one thing the shared table exists to catch. The Deployment is
  `Recreate` for the same reason;
* **`auth.required` with no token** — an explicit requirement with
  nothing behind it.

A coordinator with no token at all renders, because a Service reachable
only from inside a namespace with a NetworkPolicy is a legitimate
configuration, but `NOTES.txt` says plainly that anyone who can reach it
can read the job and write to the log.

## Values worth understanding

| value | default | why you would change it |
|---|---|---|
| `agents.replicaCount` | `3` | the whole point: `m` agents finish about `m` times faster |
| `agents.threads` | `2` | lanes per pod; one per allotted CPU |
| `agents.idleWhenSolved` | `true` | agents exit when the instance is solved, and a Deployment would restart them into a loop; this makes them idle instead, so you scale to zero when the campaign is done |
| `coordinator.persistence.enabled` | `false` | a replacement pod starts from the last pod's check-in log instead of waiting for the fleet to refill it |
| `coordinator.idleTimeout` | `5m` | a channel silent this long is dropped; the hub pings at a third of it, so **any proxy in front must allow a longer idle timeout** |
| `ingress.enabled` | `false` | only needed for agents outside the cluster |
| `networkPolicy.enabled` | `false` | writes the topology down: agents may not be connected to at all |
| `serviceMonitor.enabled` | `false` | scrapes `/metrics` (behind the same token) |

## The ingress, if agents live outside the cluster

The reverse channel is an HTTP/1.1 upgrade. Two settings decide whether
it works at all, and the chart's default annotations are the nginx
spelling of both:

* the proxy must pass `Upgrade` and `Connection` through;
* its read timeout must exceed the hub's ping period
  (`coordinator.idleTimeout / 3`, i.e. 100 s by default). Below that,
  channels are closed under the agents — which costs a reconnect with
  backoff and no work, but fills the logs.

Then point external agents at it:

```sh
export CA_COORDINATOR_URL=https://rho.example.com CA_COORDINATOR_TOKEN=…
ca work --node "$(hostname)" --threads "$(nproc)"
```

## Operating it

```sh
kubectl logs -f deploy/rho-ca-coordinator          # progress, as JSON lines
kubectl scale deploy/rho-ca-coordinator-agent --replicas=50
helm test rho                                      # runs `ca coord-status` in-cluster
```

`helm test` is not a port check: `coord-status` fetches the job document
over the URL and merges a delta through `/v1/sync`, so a pass means
routing, the token, the job and the sync path all work.

**Losing the coordinator loses no work.** Agents keep walking their
claimed units and keep their own tables; when the pod comes back they
reconverge. Evicting it, rolling it, or letting the node die are all
ordinary events, which is why it runs as a plain single-replica
Deployment with no leader election and no database.

**Losing an agent** costs the unfinished part of one work unit: its
lease expires and another agent resumes from the last cursor anybody
reported. That is the whole reason spot capacity is fine here.

## Images

`deploy/docker/Dockerfile` builds both from the repository root:

```sh
docker build -f deploy/docker/Dockerfile --target coordinator -t ghcr.io/aburan28/ca-coordinator:0.1.0 .
docker build -f deploy/docker/Dockerfile --target agent       -t ghcr.io/aburan28/ca-agent:0.1.0 .
```

The coordinator is a static Go binary on distroless; the agent is the C
`ca` binary. Both compile the same C sources, so the job, the
verification and the merge are one implementation on both sides of the
socket.
