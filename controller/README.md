# Campaign controller

A Kubernetes controller that reconciles `Campaign` resources
(`cryptanalysis.io/v1alpha1`) into walker Jobs scheduled by
[Kueue](https://kueue.sigs.k8s.io/). It is the compute-side counterpart of the
[ECC2K-130 coordinator](../usecases/ecc2k130/README.md): the coordinator owns
the S3 corpus, the durable Redis stream and the RDS index; the controller owns
where and how many walkers run.

```text
Campaign ──▶ controller ──▶ batch/v1 Job (Indexed, suspended, queue-name label)
                 ▲               │ Kueue admits, MultiKueue dispatches
                 │               ▼
        status.json feed    walker pods: slot = RHO_SLOT_BASE + JOB_COMPLETION_INDEX
        (queue pressure,          │
         collisions)              └─▶ S3 objects ─▶ publisher API ─▶ Redis ─▶ RDS
```

## What the controller decides

| Input | Effect |
|---|---|
| `spec.workers.parallelism` | desired walkers; applied in place through Kueue elastic jobs |
| `spec.workers.slotCount` / `slotBase` | the slot range the Campaign owns; becomes Job `completions`, immutable |
| `spec.scheduling.queueName` | `kueue.x-k8s.io/queue-name`; a MultiKueue ClusterQueue dispatches to worker clusters |
| `spec.backpressure` + `coordinator.statusURL` | queue `green`/`yellow`/`red` maps to desired/yellow/red parallelism with recovery hysteresis; a stale or unreachable feed holds the current value |
| `spec.suspend`, `onCollision: Suspend` | deletes the Job and releases quota; S3 checkpoints make this safe |
| any change to image, env, resources, slot range, queue | hands over: the old Job is deleted before the successor is created so two generations never hold quota together |

Red pressure with `redParallelism: 0` deletes the Job rather than parking pods:
holding GPU quota while the coordinator refuses admissions helps nobody. When
the feed leaves red the controller waits `recoverySeconds` before restoring
parallelism so a flapping queue cannot thrash the fleet. Decreases apply
immediately.

Walker pods are created suspended, as Kueue requires, and never unsuspended by
the controller. `status.conditions[Admitted]` flips when Kueue does.
Disruptions (preemption, drains) are ignored by the Job's pod failure policy
so they never consume `backoffLimit`; genuine crashes restart in place.

## Walker contract

Every walker container receives:

| variable | value |
|---|---|
| `RHO_CURVE`, `RHO_CAMPAIGN`, `ECC2K130_CAMPAIGN_ID` | from `spec.target` |
| `ECC_BUCKET`, `AWS_REGION`, `AWS_DEFAULT_REGION` | from `spec.coordinator` |
| `RHO_QUEUE_PUBLISH_URL`, `RHO_QUEUE_PUBLISH_TOKEN` | publisher endpoint; token from `tokenSecretRef` |
| `RHO_SLOT_BASE`, `RHO_SLOT_COUNT`, `JOB_COMPLETION_INDEX` | the walker owns slot `RHO_SLOT_BASE + JOB_COMPLETION_INDEX` |
| `RHO_SPOOL_DIR` | emptyDir for objects retained while the publisher returns 429/5xx |
| `RHO_WORKER_ID`, `RHO_NODE_NAME` | pod and node names for `rho_slots.worker_id` |
| `AWS_ROLE_ARN`, `AWS_WEB_IDENTITY_TOKEN_FILE`, … | only with `spec.workers.webIdentity` |

The walker must upload immutable DP objects to `ECC_BUCKET`, then call the
publisher (or `usecases/ecc2k130/publish.py`) and treat exit 75 as "retain the
spool". Pods carry the `cryptanalysis.io/ecc2k130-publisher-client: "true"`
label the coordinator NetworkPolicy expects. `spec.workers.env` may not
override the contract; collisions are dropped with a warning event.

## Install

```sh
helm upgrade --install cryptanalysis-operator controller/deploy/helm/cryptanalysis-operator \
  --namespace cryptanalysis-system --create-namespace
kubectl apply -f controller/deploy/examples/kueue-queues.yaml
kubectl -n cryptanalysis create secret generic ecc2k130-walker --from-literal=publish-token=…
kubectl apply -f controller/deploy/examples/campaign-ecc2k130.yaml
kubectl get campaigns -n cryptanalysis
```

Helm installs `crds/` once and never upgrades it; run
`kubectl apply --server-side -f controller/deploy/helm/cryptanalysis-operator/crds/`
on upgrades. Set `watchNamespace` to scope the controller to one namespace with
a Role instead of a ClusterRole.

### Kueue and MultiKueue

Kueue v0.19 or newer. For in-place resizing enable the
`ElasticJobsViaWorkloadSlices` feature gate (Beta, on by default since 0.18);
otherwise set `spec.scheduling.elastic: false` and the controller recreates
the Job to resize it.

For several GPU clusters, run Kueue in MultiKueue mode: the controller and
Campaigns live in the manager cluster, the LocalQueue points at a ClusterQueue
with a MultiKueue `AdmissionCheck`, and Kueue mirrors the worker cluster's Job
status back so `status.readyWorkers` stays truthful. Each worker cluster needs
the publisher token Secret and network reachability to a publisher: either the
coordinator's TLS gateway or a publisher-only install of the coordinator chart
(`consumer.enabled=false`, optionally `publisher.kind=DaemonSet`) that
publishes into the shared MemoryDB stream.

### Identity

Walkers upload to S3, so they need AWS credentials. On EKS give
`spec.workers.serviceAccountName` an IRSA annotation. On GKE or any other
cluster set `spec.workers.webIdentity.roleArn`; the controller mounts a
projected token with audience `sts.amazonaws.com` and sets the `AWS_*`
variables, exactly like the coordinator chart's `identity.mode: gke`. The
controller itself needs no cloud credentials; it only reads the public
status feed and the Kubernetes API.

## Development

```sh
make -C controller generate   # deepcopy + CRD (controller-gen)
make -C controller test       # unit tests: policy, Job builder, reconciler, CRD validation
make -C controller helm       # lint, render and kubeconform the operator chart
make -C controller image
```

The tests validate the generated CRD with the API server's own validation
package (including CEL compilation and cost budgets) and check the shipped
example against the schema, so the CRD, the Go types and the documentation
cannot drift apart.
