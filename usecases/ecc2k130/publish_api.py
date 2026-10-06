"""Narrow authenticated API for publishing durable S3 object references."""

from __future__ import annotations

import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from handler import (
    CHECKPOINT_KEY_RE,
    MAX_CHECKPOINT_OBJECT_BYTES,
    MAX_DP_OBJECT_BYTES,
    MAX_SLOT,
    Config,
)
from stream import Backpressure, RedisStreamQueue

MAX_BODY = 8192


class Publisher:
    def __init__(self, config, queue, s3):
        self.config = config
        self.queue = queue
        self.s3 = s3
        self._versioning_checked = False

    def _require_versioning(self):
        if self._versioning_checked:
            return
        status = self.s3.get_bucket_versioning(Bucket=self.config.bucket)
        if status.get("Status") != "Enabled":
            raise ValueError("mutable checkpoints require S3 versioning=Enabled")
        self._versioning_checked = True

    def publish(self, payload):
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        bucket = str(payload.get("bucket") or self.config.bucket)
        if bucket != self.config.bucket:
            raise ValueError("bucket does not match ECC_BUCKET")
        key = str(payload.get("key") or "")
        if not key:
            raise ValueError("key is required")
        version_id = str(payload.get("versionId") or "")
        request = {"Bucket": bucket, "Key": key}
        if version_id:
            request["VersionId"] = version_id
        head = self.s3.head_object(**request)
        size = int(head["ContentLength"])

        checkpoint = CHECKPOINT_KEY_RE.fullmatch(key)
        if key.endswith(".bin"):
            if size <= 0 or size % 32:
                raise ValueError("DP object must contain whole 32-byte records")
            limit = getattr(
                getattr(self.queue, "config", None),
                "max_dp_bytes",
                MAX_DP_OBJECT_BYTES,
            )
            if size > limit:
                raise ValueError(f"DP object exceeds {limit} byte limit")
            records = size // 32
            if self.config.campaign_id:
                self.s3.head_object(Bucket=bucket, Key=key + ".json")
        elif checkpoint:
            if int(checkpoint.group(1)) > MAX_SLOT:
                raise ValueError("checkpoint slot exceeds the 16-bit run-id space")
            records = 0
            limit = getattr(
                getattr(self.queue, "config", None),
                "max_checkpoint_bytes",
                MAX_CHECKPOINT_OBJECT_BYTES,
            )
            if size > limit:
                raise ValueError(f"checkpoint exceeds {limit} byte limit")
            if self.config.campaign_id:
                self.s3.head_object(Bucket=bucket, Key=key + ".json")
            if checkpoint.group(2) is None:
                self._require_versioning()
                version_id = str(head.get("VersionId") or version_id)
                if not version_id or version_id == "null":
                    raise ValueError("mutable checkpoint requires S3 versioning")
            else:
                version_id = ""
        else:
            raise ValueError("unsupported ECC2K-130 object key")

        modified = head.get("LastModified")
        event_time = (
            modified.isoformat()
            if modified is not None
            else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        return self.queue.publish(
            bucket,
            key,
            size=size,
            records=records,
            event_time=event_time,
            version_id=version_id,
        )


def handler(publisher, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ecc2k130-publisher/1"

        def _json(self, status, value, headers=None):
            body = (json.dumps(value, sort_keys=True) + "\n").encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, item in (headers or {}).items():
                self.send_header(key, item)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/healthz":
                self._json(404, {"error": "not found"})
                return
            try:
                publisher.queue.client.ping()
                self._json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001 - dependency health response
                self._json(503, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if self.path != "/v1/objects":
                self._json(404, {"error": "not found"})
                return
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + token
            if not hmac.compare_digest(supplied, expected):
                self._json(401, {"error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                self._json(413, {"error": "invalid request size"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
                result = publisher.publish(payload)
                self._json(200 if result["duplicate"] else 201, result)
            except Backpressure as exc:
                self._json(
                    429,
                    {
                        "error": "backpressure",
                        "pressure": exc.state,
                        "messages": exc.messages,
                        "bytes": exc.queued_bytes,
                    },
                    {"Retry-After": "30"},
                )
            except (TypeError, ValueError) as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - fail closed for dependencies
                self._json(503, {"error": str(exc)}, {"Retry-After": "30"})

        def log_message(self, format, *args):
            print(
                json.dumps(
                    {
                        "remote": self.client_address[0],
                        "request": self.requestline,
                        "message": format % args,
                    },
                    sort_keys=True,
                )
            )

    return Handler


def main():
    import boto3

    config = Config.from_env()
    if not config.bucket:
        raise SystemExit("ECC_BUCKET is required")
    token = os.environ.get("RHO_QUEUE_PUBLISH_TOKEN", "")
    if not token:
        raise SystemExit("RHO_QUEUE_PUBLISH_TOKEN is required")
    publisher = Publisher(config, RedisStreamQueue.from_env(), boto3.client("s3"))
    listen = os.environ.get("RHO_QUEUE_PUBLISH_LISTEN", "0.0.0.0")
    port = int(os.environ.get("RHO_QUEUE_PUBLISH_PORT", "8080"))
    server = ThreadingHTTPServer((listen, port), handler(publisher, token))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
