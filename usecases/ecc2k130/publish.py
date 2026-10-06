"""Worker-side client for the narrow Redis publisher API."""

import argparse
import json
import os
import urllib.error
import urllib.request

TEMPFAIL = 75


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default=os.environ.get("ECC_BUCKET"), required=False)
    parser.add_argument("--key", required=True)
    parser.add_argument("--version-id", default="")
    parser.add_argument("--url", default=os.environ.get("RHO_QUEUE_PUBLISH_URL"))
    parser.add_argument("--token", default=os.environ.get("RHO_QUEUE_PUBLISH_TOKEN"))
    args = parser.parse_args(argv)
    if not args.bucket:
        parser.error("--bucket or ECC_BUCKET is required")
    if not args.url or not args.token:
        parser.error("RHO_QUEUE_PUBLISH_URL and RHO_QUEUE_PUBLISH_TOKEN are required")
    body = json.dumps(
        {"bucket": args.bucket, "key": args.key, "versionId": args.version_id}
    ).encode()
    request = urllib.request.Request(
        args.url.rstrip("/") + "/v1/objects",
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + args.token,
            "Content-Type": "application/json",
        },
    )
    try:
        response = urllib.request.urlopen(request, timeout=20)
        result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        result = json.loads(exc.read() or b"{}")
        print(json.dumps(result, sort_keys=True))
        return TEMPFAIL if exc.code == 429 or exc.code >= 500 else 1
    except (OSError, urllib.error.URLError) as exc:
        print(json.dumps({"error": str(exc), "retryable": True}, sort_keys=True))
        return TEMPFAIL
    print(json.dumps({"status": "queued", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
