"""Enqueue existing checkpoints once when cutting status publication over."""

import argparse
import json

from handler import CHECKPOINT_KEY_RE


def checkpoint_keys(s3, bucket):
    token = None
    while True:
        args = {"Bucket": bucket, "Prefix": "ckpt/"}
        if token:
            args["ContinuationToken"] = token
        page = s3.list_objects_v2(**args)
        for item in page.get("Contents", []):
            if CHECKPOINT_KEY_RE.fullmatch(item["Key"]):
                yield item["Key"]
        if not page.get("IsTruncated"):
            return
        token = page["NextContinuationToken"]


def enqueue(s3, sqs, bucket, queue_url):
    sent = 0
    entries = []
    for key in checkpoint_keys(s3, bucket):
        entries.append(
            {
                "Id": str(len(entries)),
                "MessageBody": json.dumps(
                    {"bucket": bucket, "manifestKey": key}, separators=(",", ":")
                ),
            }
        )
        if len(entries) == 10:
            response = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
            if response.get("Failed"):
                raise RuntimeError(f"SQS rejected checkpoint messages: {response['Failed']}")
            sent += len(entries)
            entries = []
    if entries:
        response = sqs.send_message_batch(QueueUrl=queue_url, Entries=entries)
        if response.get("Failed"):
            raise RuntimeError(f"SQS rejected checkpoint messages: {response['Failed']}")
        sent += len(entries)
    return sent


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--queue-url", required=True)
    args = parser.parse_args(argv)

    import boto3

    sent = enqueue(
        boto3.client("s3"), boto3.client("sqs"), args.bucket, args.queue_url
    )
    print(json.dumps({"bucket": args.bucket, "checkpointMessages": sent}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
