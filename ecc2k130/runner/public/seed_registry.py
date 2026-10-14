"""Reserve public run IDs in the existing bucket-wide ECC2K-130 seed registry.

Compatible with crypto/ecc2k130/aws/seed_registry.py version 1.  Public
assignments keep one permanent owner at the gateway; the gateway never expires
or reassigns one contributor's seed range to another contributor.
"""

from __future__ import annotations

import json
import time

PREFIX = "seed-registry/curve-131/"


class RegistryError(RuntimeError):
    pass


class S3Registry:
    def __init__(self, bucket: str, stream_id: str, client=None):
        if not bucket or not stream_id or len(stream_id) > 96:
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
