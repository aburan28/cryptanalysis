"""Reserve public run IDs in the existing bucket-wide ECC2K-130 seed registry.

Compatible with crypto/ecc2k130/aws/seed_registry.py version 1.  Public
assignments keep one permanent owner at the gateway; the gateway never expires
or reassigns one contributor's seed range to another contributor.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time

PREFIX = "seed-registry/curve-131/"
ARCHIVE_PREFIX = "public-gateway/"


class RegistryError(RuntimeError):
    pass


class S3Registry:
    def __init__(self, bucket: str, stream_id: str, client=None):
        if not bucket or not re.fullmatch(r"[a-zA-Z0-9_-]{8,64}", stream_id):
            raise RegistryError("ECC_BUCKET and a short ECC_PUBLIC_STREAM_ID are required")
        self.bucket = bucket
        self.stream_id = stream_id
        if client is None:
            import boto3
            client = boto3.client("s3")
        self.client = client

    def ready(self) -> None:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=PREFIX + "config.json")
            config = json.loads(obj["Body"].read())
        except Exception as exc:
            raise RegistryError("cannot read the campaign seed registry") from exc
        if config.get("version") != 1 or config.get("state") != "ready":
            raise RegistryError("campaign seed registry is not ready")

    def reserve(self, run_id: int) -> bool:
        if not 1 <= run_id <= 65535:
            raise RegistryError("run ID is outside the 16-bit seed namespace")
        self.ready()
        stream = f"public-gateway:{self.stream_id}:run{run_id}"
        row = {"version": 1, "run_id": run_id, "stream": stream,
               "started": True, "active_owner": stream,
               "checkpoint_floor": 0, "created_at": time.time()}
        try:
            self.client.put_object(Bucket=self.bucket,
                                   Key=PREFIX + f"run-{run_id:05d}.json",
                                   Body=json.dumps(row, sort_keys=True).encode(),
                                   ContentType="application/json", IfNoneMatch="*")
            return True
        except Exception as exc:
            response = getattr(exc, "response", {})
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = response.get("Error", {}).get("Code")
            if status in (409, 412) or code in ("PreconditionFailed", "ConditionalRequestConflict"):
                return False
            raise RegistryError("cannot reserve a campaign seed identity") from exc

    def batch_key(self, run_id: int, offset: int, digest: str) -> str:
        if not 1 <= run_id <= 65535 or offset < 0 or offset % 32:
            raise RegistryError("invalid public batch identity")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RegistryError("invalid public batch digest")
        return (f"{ARCHIVE_PREFIX}{self.stream_id}/runs/{run_id:05d}/batches/"
                f"{offset:016d}-{digest}.bin")

    def fetch_batch(self, run_id: int, offset: int, digest: str, size: int) -> bytes:
        key = self.batch_key(run_id, offset, digest)
        try:
            data = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as exc:
            raise RegistryError("cannot read the durable public batch") from exc
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise RegistryError("durable public batch does not match its receipt")
        return data

    def archive_batch(self, run_id: int, offset: int, data: bytes) -> str:
        digest_bytes = hashlib.sha256(data).digest()
        digest = digest_bytes.hex()
        key = self.batch_key(run_id, offset, digest)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                                   ContentType="application/octet-stream",
                                   ChecksumSHA256=base64.b64encode(digest_bytes).decode(),
                                   IfNoneMatch="*")
        except Exception as exc:
            response = getattr(exc, "response", {})
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = response.get("Error", {}).get("Code")
            if status in (409, 412) or code in ("PreconditionFailed", "ConditionalRequestConflict"):
                if self.fetch_batch(run_id, offset, digest, len(data)) == data:
                    return key
            raise RegistryError("cannot archive the public DP batch") from exc
        return key
