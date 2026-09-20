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

MemoryDB, RDS, S3 buckets, IAM roles and the Kubernetes Secret remain external
managed resources.

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
Secrets Manager. Annotate their service accounts with the appropriate EKS IAM
roles:

```yaml
serviceAccounts:
  publisher:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::<account>:role/ecc2k-publisher
  consumer:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::<account>:role/ecc2k-consumer
  reconciler:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::<account>:role/ecc2k-reconciler
```

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
