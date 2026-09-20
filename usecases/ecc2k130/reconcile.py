"""Repair the S3→Redis dual-write window without ingesting DP bytes."""

from __future__ import annotations

import argparse
import json

from handler import CHECKPOINT_KEY_RE, ORBIT_KEY_RE, Config, _not_found, database_url
from stream import Backpressure, RedisStreamQueue


def objects(s3, bucket):
    token = None
    while True:
        args = {"Bucket": bucket, "Prefix": "dp/"}
        if token:
            args["ContinuationToken"] = token
        page = s3.list_objects_v2(**args)
        for item in page.get("Contents", []):
            if ORBIT_KEY_RE.fullmatch(item["Key"]):
                yield {
                    "key": item["Key"],
                    "versionId": "",
                    "bytes": int(item.get("Size") or 0),
                    "lastModified": item.get("LastModified"),
                }
        if not page.get("IsTruncated"):
            break
        token = page["NextContinuationToken"]

    key_marker = version_marker = None
    while True:
        args = {"Bucket": bucket, "Prefix": "ckpt/"}
        if key_marker:
            args["KeyMarker"] = key_marker
        if version_marker:
            args["VersionIdMarker"] = version_marker
        page = s3.list_object_versions(**args)
        for item in page.get("Versions", []):
            key = item["Key"]
            match = CHECKPOINT_KEY_RE.fullmatch(key)
            if not match:
                continue
            if match.group(2) is not None and not item.get("IsLatest", True):
                continue
            version_id = "" if match.group(2) is not None else str(
                item.get("VersionId") or ""
            )
            if match.group(2) is None and (
                not version_id or version_id == "null"
            ):
                status = s3.get_bucket_versioning(Bucket=bucket)
                raise RuntimeError(
                    "mutable checkpoints require S3 versioning=Enabled, got "
                    f"{status.get('Status')!r}"
                )
            yield {
                "key": key,
                "versionId": version_id,
                "bytes": int(item.get("Size") or 0),
                "lastModified": item.get("LastModified"),
            }
        if not page.get("IsTruncated"):
            break
        key_marker = page.get("NextKeyMarker")
        version_marker = page.get("NextVersionIdMarker")


def committed(connection, campaign):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT object_key FROM ecc2k130_commits WHERE campaign_id = %s",
            (campaign,),
        )
        done = {(row[0], "") for row in cur.fetchall()}
        cur.execute(
            "SELECT object_key, version_id FROM ecc2k130_checkpoint_objects "
            "WHERE campaign_id = %s",
            (campaign,),
        )
        done.update((row[0], row[1]) for row in cur.fetchall())
    connection.commit()
    return done


def reconcile(s3, queue, connection, config, limit=0):
    done = committed(connection, config.campaign)
    checked = queued = duplicate = uncommitted = invalid = 0
    invalid_keys = []
    for item in objects(s3, config.bucket):
        checked += 1
        if (item["key"], item["versionId"]) in done:
            continue
        checkpoint = CHECKPOINT_KEY_RE.fullmatch(item["key"])
        needs_marker = item["key"].endswith(".bin") or (
            checkpoint is not None and checkpoint.group(2) is not None
        )
        if config.campaign_id and needs_marker:
            try:
                s3.head_object(Bucket=config.bucket, Key=item["key"] + ".json")
            except Exception as exc:
                if not _not_found(exc):
                    raise
                uncommitted += 1
                continue
        try:
            size = item["bytes"]
            records = size // 32 if item["key"].endswith(".bin") else 0
            when = item["lastModified"]
            result = queue.publish(
                config.bucket,
                item["key"],
                size=size,
                records=records,
                event_time=when.isoformat() if when is not None else None,
                version_id=item["versionId"],
            )
        except ValueError:
            invalid += 1
            if len(invalid_keys) < 20:
                invalid_keys.append(item["key"])
            continue
        duplicate += int(result["duplicate"])
        queued += int(not result["duplicate"])
        if limit and queued >= limit:
            break
    return {
        "checked": checked,
        "queued": queued,
        "alreadyQueued": duplicate,
        "uncommitted": uncommitted,
        "invalid": invalid,
        "invalidKeys": invalid_keys,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    import boto3
    import psycopg

    config = Config.from_env()
    config.validate()
    secrets = boto3.client("secretsmanager")
    connection = psycopg.connect(
        database_url(config, secrets), connect_timeout=30, autocommit=False
    )
    try:
        result = reconcile(
            boto3.client("s3"),
            RedisStreamQueue.from_env(),
            connection,
            config,
            limit=max(0, args.limit),
        )
    except Backpressure as exc:
        print(
            json.dumps(
                {
                    "status": "backpressure",
                    "pressure": exc.state,
                    "messages": exc.messages,
                    "bytes": exc.queued_bytes,
                },
                sort_keys=True,
            )
        )
        return 75
    finally:
        connection.close()
    print(json.dumps({"status": "ok", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
