"""Idempotently add the ECC2K-130 immutable-payload S3 notification.

Unlike ``put-bucket-notification-configuration`` with a handwritten document,
this preserves unrelated Lambda, SNS, SQS, and EventBridge notifications
already configured on the campaign bucket.
"""

import argparse
import json

NOTIFICATION_ID = "cryptanalysis-ecc2k130-payloads"
CHECKPOINT_NOTIFICATION_ID = "cryptanalysis-ecc2k130-checkpoints"


def merged_configuration(current, queue_arn):
    keep = {
        key: value
        for key, value in current.items()
        if key
        in (
            "TopicConfigurations",
            "QueueConfigurations",
            "LambdaFunctionConfigurations",
            "EventBridgeConfiguration",
        )
    }
    queues = [
        item
        for item in keep.get("QueueConfigurations", [])
        if item.get("Id") not in (NOTIFICATION_ID, CHECKPOINT_NOTIFICATION_ID)
    ]
    for ident, prefix, suffix in (
        (NOTIFICATION_ID, "dp/", ".bin"),
        (CHECKPOINT_NOTIFICATION_ID, "ckpt/", ".ck"),
    ):
        queues.append(
            {
                "Id": ident,
                "QueueArn": queue_arn,
                "Events": ["s3:ObjectCreated:*"],
                "Filter": {
                    "Key": {
                        "FilterRules": [
                            {"Name": "prefix", "Value": prefix},
                            {"Name": "suffix", "Value": suffix},
                        ]
                    }
                },
            }
        )
    keep["QueueConfigurations"] = queues
    return keep


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--queue-arn", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import boto3

    s3 = boto3.client("s3")
    current = s3.get_bucket_notification_configuration(Bucket=args.bucket)
    merged = merged_configuration(current, args.queue_arn)
    if args.dry_run:
        print(json.dumps(merged, indent=2, sort_keys=True))
        return 0
    s3.put_bucket_notification_configuration(
        Bucket=args.bucket, NotificationConfiguration=merged
    )
    print(
        json.dumps(
            {
                "bucket": args.bucket,
                "notificationId": NOTIFICATION_ID,
                "queueArn": args.queue_arn,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
