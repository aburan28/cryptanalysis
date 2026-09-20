"""Long-running Redis Streams consumer for the ECC2K-130 index."""

from __future__ import annotations

import json
import os
import signal
import time

from handler import (
    Config,
    PostgresIndex,
    database_url,
    process_message,
    publish_status,
)
from stream import (
    PermanentMessageError,
    QueueConfig,
    RedisStreamQueue,
    StreamConsumer,
)


class IndexService:
    def __init__(
        self, config, queue, s3, index, status_every=180, connection_factory=None
    ):
        self.config = config
        self.queue = queue
        self.s3 = s3
        self.index = index
        self.connection_factory = connection_factory
        self.consumer = StreamConsumer(queue)
        self.status_every = status_every
        self.last_status = 0.0

    def process(self, fields):
        try:
            payload = {
                "bucket": fields["bucket"],
                "manifestKey": fields["key"],
                "eventTime": fields.get("eventTime"),
                "versionId": fields.get("versionId"),
            }
        except KeyError as exc:
            raise PermanentMessageError(f"queue entry is missing {exc}") from exc
        try:
            results = process_message(payload, self.config, self.s3, self.index)
        except (TypeError, ValueError) as exc:
            raise PermanentMessageError(str(exc)) from exc
        except Exception:
            if (
                self.connection_factory is not None
                and getattr(self.index.connection, "closed", False)
            ):
                replacement = PostgresIndex(
                    self.connection_factory(), self.config.campaign
                )
                replacement.assert_schema()
                self.index = replacement
            raise
        if any(int(row.get("collisions") or 0) for row in results):
            self.publish()
        return results

    def publish(self):
        pressure = self.queue.refresh_pressure()
        status = publish_status(self.config, self.s3, self.index, pressure)
        self.last_status = time.monotonic()
        print(json.dumps({"status": "published", "snapshot": status}, sort_keys=True))
        return status

    def run_once(self):
        result = self.consumer.consume_once(self.process)
        if time.monotonic() - self.last_status >= self.status_every:
            self.publish()
        print(json.dumps(result, sort_keys=True))
        return result


def dependencies():
    import boto3
    import psycopg

    config = Config.from_env()
    config.validate()
    queue_config = QueueConfig.from_env()
    queue_config.validate()
    secrets = boto3.client("secretsmanager")
    url = database_url(config, secrets)

    def connect():
        return psycopg.connect(url, connect_timeout=30, autocommit=False)

    index = PostgresIndex(connect(), config.campaign)
    index.assert_schema()
    return IndexService(
        config=config,
        queue=RedisStreamQueue.from_env(queue_config),
        s3=boto3.client("s3"),
        index=index,
        status_every=int(os.environ.get("RHO_STATUS_EVERY", "180")),
        connection_factory=connect,
    )


def main():
    service = dependencies()
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    delay = 1.0
    while not stopping:
        try:
            service.run_once()
            delay = 1.0
        except Exception as exc:  # noqa: BLE001 - service dependency retry loop
            print(
                json.dumps(
                    {
                        "status": "dependency-error",
                        "error": str(exc),
                        "retryInSeconds": delay,
                    },
                    sort_keys=True,
                )
            )
            time.sleep(delay)
            delay = min(30.0, delay * 2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
