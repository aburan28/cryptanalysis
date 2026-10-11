# ECC2K-130 coordinator Helm chart

Deploys three stateless coordinator workloads:

| workload | role |
|---|---|
| publisher Deployment + Service | authenticates walkers, validates S3 objects, applies Redis backpressure |
| consumer Deployment | Redis consumer group → verified transactional RDS index |
| reconciler CronJob | repairs the S3-before-Redis dual-write window |

Consumer pods run an advisory-lock-protected migration init container before
touching RDS. The migration receives a dedicated DDL-capable database URL that
is not exposed to the runtime container.

MemoryDB, RDS, S3 buckets, IAM roles, OIDC providers and the Kubernetes Secret
remain external managed resources. The chart runs on EKS (IRSA or Pod
Identity), GKE (Workload Identity plus AWS federation) and any cluster with a
public OIDC issuer; see [Cloud identity](#cloud-identity).

## Required Secret

Create it before installing. Do not put credentials in Helm values:

```sh
kubectl -n cryptanalysis create secret generic ecc2k130-coordinator \
  --from-literal=producer-redis-url='rediss://producer:password@memorydb:6379' \
  --from-literal=consumer-redis-url='rediss://consumer:password@memorydb:6379' \
  --from-literal=publish-token="$(openssl rand -hex 32)" \
  --from-literal=migration-database-url='postgresql://owner:password@host/db?sslmode=require'
```

To use a complete libpq URL, add `--from-literal=database-url=...` and set:

```yaml
existingSecret:
  runtimeDatabaseUrlKey: database-url
```

Otherwise the runtime consumer and reconciler resolve `rds.secretId` through
Secrets Manager using the pod's AWS identity.

## Cloud identity

The data plane is AWS, so every pod needs AWS credentials whichever cloud
hosts the cluster. `identity.mode` selects how they arrive; the per-component
IAM roles are always declared the same way:

```yaml
serviceAccounts:
  publisher:
    awsRoleArn: arn:aws:iam::<account>:role/ecc2k-publisher
  consumer:
    awsRoleArn: arn:aws:iam::<account>:role/ecc2k-consumer
  reconciler:
    awsRoleArn: arn:aws:iam::<account>:role/ecc2k-reconciler
```

| `identity.mode` | cluster | what the chart renders |
|---|---|---|
| `irsa` (default) | Amazon EKS | `eks.amazonaws.com/role-arn`, `audience`, `token-expiration` and `sts-regional-endpoints` annotations; the EKS pod identity webhook injects the token and `AWS_*` environment |
| `gke` | GKE Standard or Autopilot | `iam.gke.io/gcp-service-account` when `gcpServiceAccount` is set, the `iam.gke.io/gke-metadata-server-enabled` node selector, and a projected token federated into the AWS roles |
| `web-identity` | AKS, on-prem, any cluster with a public OIDC issuer | the projected token federation only |
| `none` | anything | only `serviceAccounts.*.annotations`; use with EKS Pod Identity associations, instance profiles, or externally injected credentials |

Changing a role rolls the affected pods: the rendered annotations feed the
`checksum/external-config` pod annotation.

### EKS with IRSA

Each role's trust policy must accept the cluster's OIDC provider and the exact
service-account subject:

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::<account>:oidc-provider/oidc.eks.<region>.amazonaws.com/id/<id>" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "oidc.eks.<region>.amazonaws.com/id/<id>:aud": "sts.amazonaws.com",
      "oidc.eks.<region>.amazonaws.com/id/<id>:sub": "system:serviceaccount:cryptanalysis:ecc2k130-ecc2k130-coordinator-publisher"
    }
  }
}
```

The default `podSecurityContext.fsGroup` is what lets the non-root containers
read the projected token; keep it. Components without an `awsRoleArn` fall
back to the node instance role. For EKS Pod Identity, set `identity.mode:
none` and create the pod identity associations against the rendered service
account names.

### GKE

GKE Workload Identity Federation only issues Google credentials, so AWS access
is federated directly: pods mount a Kubernetes token with audience
`sts.amazonaws.com` and boto3 exchanges it through
`AssumeRoleWithWebIdentity`. Register the cluster's issuer once in AWS:

```sh
aws iam create-open-id-connect-provider \
  --url https://container.googleapis.com/v1/projects/<project>/locations/<location>/clusters/<cluster> \
  --client-id-list sts.amazonaws.com
```

and trust it in each role with the same `aud`/`sub` conditions as above, using
`container.googleapis.com/v1/projects/<project>/locations/<location>/clusters/<cluster>`
as the condition key prefix. Then install with:

```yaml
identity:
  mode: gke
  gcp:
    requireMetadataServer: true   # false on Autopilot
serviceAccounts:
  publisher:
    awsRoleArn: arn:aws:iam::<account>:role/ecc2k-publisher
    gcpServiceAccount: ecc2k-publisher@<project>.iam.gserviceaccount.com   # optional
```

`gcpServiceAccount` is only needed when a component must also call Google
APIs; direct IAM bindings on the Kubernetes principal work without it.
Networking to MemoryDB and RDS from GKE (VPN, Interconnect, or PrivateLink
equivalents) is outside the chart.

### Publisher-only walker clusters

A cluster that only hosts walkers can run just the admission tier and publish
into the shared MemoryDB stream, leaving the RDS index to the primary release:

```yaml
consumer:
  enabled: false
reconciler:
  enabled: false
rds:
  host: ""
existingSecret:
  consumerRedisUrlKey: ""
  migrationDatabaseUrlKey: ""
```

The Secret then only needs `producer-redis-url` and `publish-token`. Combine
with `publisher.kind: DaemonSet` for node-local publishing.

### Other clusters

`identity.mode: web-identity` renders the same projected token and `AWS_*`
environment for any cluster whose OIDC issuer AWS can reach (AKS with
`--enable-oidc-issuer`, kubeadm with a published issuer, and so on).

Minimum AWS access:

- publisher: `s3:GetObject` (which authorizes `HeadObject`) and
  `s3:GetObjectVersion` on campaign `dp/` and `ckpt/`, plus
  `s3:GetBucketVersioning` for mutable checkpoints;
- consumer: `s3:GetObject` and `s3:GetObjectVersion` on campaign objects,
  status-bucket `s3:PutObject`, and Secrets Manager read when the runtime
  `DATABASE_URL` is not supplied;
- reconciler: `s3:ListBucket`, `s3:ListBucketVersions`,
  `s3:GetBucketVersioning`, `s3:GetObject`, plus runtime database access.

All pods also need network reachability to MemoryDB and RDS.

## Install

```sh
helm upgrade --install ecc2k130 \
  usecases/ecc2k130/deploy/helm/ecc2k130-coordinator \
  --namespace cryptanalysis --create-namespace \
  --set image.repository=ghcr.io/aburan28/cryptanalysis-ecc2k130 \
  --set image.tag=<immutable-tag> \
  -f production-values.yaml
```

Pin `image.digest` for production. The chart defaults to two publishers and
two consumers, strict pod security contexts, PodDisruptionBudgets, a
publisher NetworkPolicy and a ten-minute reconciliation schedule. Label
authorized in-namespace walker pods with:

```yaml
cryptanalysis.io/ecc2k130-publisher-client: "true"
```

The chart intentionally exposes only a ClusterIP Service. If callers are
outside the cluster, place a separately managed TLS-enforcing gateway in front
and add its namespace/pod selectors under
`networkPolicy.additionalPublisherIngress`; never send the reusable bearer
token over plaintext HTTP. In namespaces with default-deny egress, provide
environment-specific DNS/S3/MemoryDB/RDS rules under `networkPolicy.egress`;
Kubernetes policies cannot allow AWS services by hostname.

Run the Helm test:

```sh
helm test ecc2k130 -n cryptanalysis
```

After rotating values in the external Secret, force a controlled rollout:

```sh
helm upgrade ecc2k130 \
  usecases/ecc2k130/deploy/helm/ecc2k130-coordinator \
  --reuse-values --set-string rolloutNonce="$(date +%s)"
```

## Worker endpoint

In-cluster workers use:

```text
RHO_QUEUE_PUBLISH_URL=http://ecc2k130-ecc2k130-coordinator-publisher.cryptanalysis.svc
RHO_QUEUE_PUBLISH_TOKEN=<publish-token>
```

## Node-local publisher (DaemonSet)

When walkers run in the same cluster, a publisher on every walker node keeps
admission and backpressure decisions local and removes a cross-node hop from
the hot path:

```yaml
publisher:
  kind: DaemonSet
  nodeSelector:
    cryptanalysis.io/walker-pool: "true"   # Kubernetes selects by label, not annotation
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists
```

In this mode the Service defaults to `internalTrafficPolicy: Local`, so the
unchanged `RHO_QUEUE_PUBLISH_URL` reaches the publisher on the walker's own
node and fails fast (retryable, spool retained) on nodes without one. The
publisher PodDisruptionBudget is skipped because drains ignore DaemonSet pods.
Set `publisher.hostPort` to additionally expose `http://$(HOST_IP):<port>`;
Kubernetes rejects DaemonSet `maxSurge` with a hostPort, and hostPort traffic
bypasses the pod NetworkPolicy on some CNIs, so allow the node CIDR under
`networkPolicy.additionalPublisherIngress` if you use it. The consumer stays
a Deployment: its scale is bounded by RDS connections and stream batch size,
not by node count.

Workers never receive Redis credentials. HTTP 429 and 5xx responses are
retryable and mean retain the local spool. The coordinator will not accept an
object above the configured hard cap or from a bucket other than
`campaign.bucket`.

## Scaling and backpressure

Scale consumers horizontally; they share Redis consumer group `indexers`.
Watch the public status document's `queue` block and MemoryDB alarms:

- yellow should trigger scale-out before the hard limit;
- red intentionally stops publisher admission;
- dead-letter count must alert;
- do not bypass red or apply approximate stream trimming.

The chart does not deploy an HPA based on CPU because queue lag—not CPU—is the
honest scaling signal. Integrate KEDA only after validating its Redis Streams
scaler against the chosen MemoryDB cluster topology.
