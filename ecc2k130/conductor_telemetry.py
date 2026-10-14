#!/usr/bin/env python3
"""Read ECC2K slot receipts or Codex hook events and report bounded observations.

The Conductor record contains codes, identifiers, and a digest of owner-held
evidence. Slot JSON, prompts, tool arguments, credentials, and transcripts are
never sent to the shared control plane. This process only reads AWS state.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid


SAFE_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")
SLOT_KEY = re.compile(r"(?:^|/)slots/slot-([0-9]{5})\.json$")
STATES = {"active", "idle", "retired", "solved", "error"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_evidence(root, event_id, value, dry_run=False):
    """Persist the exact canonical context under its public event ID locally."""
    contents = canonical(value)
    checksum = hashlib.sha256(contents).hexdigest()
    if dry_run:
        return checksum
    directory = Path(root).expanduser()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    if not re.fullmatch(r"[a-f0-9]{32}", event_id):
        raise ValueError("invalid evidence event ID")
    path = directory / (event_id + ".json")
    temporary = directory / (event_id + ".tmp-" + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(contents)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return checksum


def stable_id(*parts):
    return hashlib.sha256("\0".join(map(str, parts)).encode()).hexdigest()[:32]


def iso_epoch(seconds):
    return dt.datetime.fromtimestamp(int(seconds), dt.timezone.utc).isoformat().replace("+00:00", "Z")


def aws_json(*args):
    result = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("AWS read failed (exit %d)" % result.returncode)
    return json.loads(result.stdout)


def s3_slots(bucket, prefix):
    path = (prefix.strip("/") + "/" if prefix.strip("/") else "") + "slots/"
    keys = aws_json("s3api", "list-objects-v2", "--bucket", bucket, "--prefix", path,
                    "--query", "Contents[].Key") or []
    for key in keys:
        match = SLOT_KEY.search(key)
        if not match or not key.startswith(path):
            continue
        with tempfile.TemporaryDirectory(prefix="ecc2k-slot-read-") as tmp:
            destination = str(Path(tmp) / "slot.json")
            result = subprocess.run(["aws", "s3api", "get-object", "--bucket", bucket,
                                     "--key", key, destination, "--output", "json"],
                                    capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError("AWS slot read failed (exit %d)" % result.returncode)
            item = json.loads(Path(destination).read_text())
        item["slot"] = int(match.group(1))
        yield item


def ddb_value(value):
    if "S" in value:
        return value["S"]
    if "N" in value:
        try:
            return int(value["N"])
        except ValueError:
            return value["N"]
    if "BOOL" in value:
        return value["BOOL"]
    if "NULL" in value:
        return None
    if "M" in value:
        return {key: ddb_value(inner) for key, inner in value["M"].items()}
    if "L" in value:
        return [ddb_value(inner) for inner in value["L"]]
    raise ValueError("unsupported DynamoDB attribute type")


def dynamo_slots(table):
    response = aws_json("dynamodb", "scan", "--table-name", table)
    for raw in response.get("Items", []):
        yield {key: ddb_value(value) for key, value in raw.items()}


def reason_for(item):
    reason = str(item.get("reason", ""))
    if reason == "reference mismatch":
        return "reference_mismatch", "stop"
    if reason == "checkpoint refused by the client":
        return "checkpoint_refused", "retire_slot"
    if re.fullmatch(r"repeated exit [0-9]+", reason):
        return "repeated_client_exit", "stop"
    if item.get("state") == "retired":
        return "slot_retired", "retire_slot"
    if item.get("state") == "error":
        return "worker_error", "stop"
    return None


def slot_observations(item, scope, now, revision=""):
    slot = item.get("slot")
    if not isinstance(slot, int) or not 0 <= slot <= 65534:
        raise ValueError("invalid ECC2K slot number")
    state = item.get("state")
    if state not in STATES:
        state = "unknown"
    lease = int(item.get("leaseUntil") or 0)
    status = "stale" if state == "active" and lease < now else state
    worker_run_id = "ecc2k130:%s:slot-%05d" % (scope, slot)
    evidence_sha256 = digest(item)
    changed_at = int(item.get("updatedAt") or item.get("claimedAt") or
                     item.get("createdAt") or 0)
    if status == "stale":
        changed_at = max(changed_at, lease)
    if changed_at <= 0:
        # Old records without a timestamp still get a stable observation.
        changed_at = 1
    base = {"source": "ecc2k_worker", "worker_run_id": worker_run_id,
            "evidence_sha256": evidence_sha256, "observed_at": iso_epoch(changed_at)}
    if revision:
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("source revision must be a full git SHA")
        base["source_revision"] = revision
    status_event = dict(base, kind="worker.status", status=status,
                        event_id=stable_id(worker_run_id, "status", status, evidence_sha256))
    yield status_event
    reason = reason_for(item)
    if reason:
        reason_code, action = reason
        yield dict(base, kind="safety.flag", rule_id="ecc2k.slot_guard",
                   rule_version="worker/v1", action=action, reason_code=reason_code,
                   event_id=stable_id(worker_run_id, "safety", reason_code, evidence_sha256))


def post(event, args):
    if args.dry_run:
        print(json.dumps(event, sort_keys=True))
        return
    if not args.endpoint or not args.project or not args.token_file:
        raise ValueError("CONDUCTOR_ENDPOINT, CONDUCTOR_PROJECT, and CONDUCTOR_TOKEN_FILE are required")
    parsed = urllib.parse.urlsplit(args.endpoint)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Conductor endpoint must be an HTTPS URL without embedded credentials")
    if not SAFE_ID.fullmatch(args.project):
        raise ValueError("invalid Conductor project")
    token_path = Path(args.token_file)
    if token_path.stat().st_mode & 0o077:
        raise ValueError("Conductor token file must be owner-only")
    token = token_path.read_text().strip()
    if not token:
        raise ValueError("Conductor token file is empty")
    url = args.endpoint.rstrip("/") + "/v1/projects/" + urllib.parse.quote(args.project, safe="") + "/external-observations"
    request = urllib.request.Request(url, data=canonical(event), method="POST",
                                     headers={"Authorization": "Bearer " + token,
                                              "Content-Type": "application/json"})
    context = ssl.create_default_context(cafile=args.ca_file) if args.ca_file else ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, context=context, timeout=10) as response:
            if response.status not in (200, 201):
                raise RuntimeError("Conductor returned HTTP %d" % response.status)
    except urllib.error.HTTPError as error:
        # Response bodies and request headers can contain private information.
        raise RuntimeError("Conductor returned HTTP %d" % error.code) from None


def context_path(root, session, turn):
    return Path(root) / (stable_id(session, turn) + ".json")


def save_prompt_context(payload, args):
    root = Path(args.context_dir).expanduser()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    record = {"session_id": payload.get("session_id", ""),
              "turn_id": payload.get("turn_id", ""),
              "prompt": payload.get("prompt", ""),
              "prompt_sha256": hashlib.sha256(str(payload.get("prompt", "")).encode()).hexdigest(),
              "transcript_path": payload.get("transcript_path")}
    path = context_path(root, record["session_id"], record["turn_id"])
    temporary = path.with_suffix(".tmp-" + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(record, handle, sort_keys=True)
    os.replace(temporary, path)


def codex_hook(payload, args):
    name = payload.get("hook_event_name")
    if name == "UserPromptSubmit":
        save_prompt_context(payload, args)
        return
    if name != "PermissionRequest":
        return
    session = str(payload.get("session_id", ""))
    turn = str(payload.get("turn_id", ""))
    tool = str(payload.get("tool_name", ""))
    if not session or not turn or not tool:
        return
    path = context_path(Path(args.context_dir).expanduser(), session, turn)
    prompt_context = {}
    if path.exists():
        prompt_context = json.loads(path.read_text())
    context = {"hook_event": "PermissionRequest", "session_id": session,
               "turn_id": turn, "tool_name": tool,
               "tool_input": payload.get("tool_input"),
               "permission_mode": payload.get("permission_mode"),
               "prompt_context": prompt_context,
               "transcript_path": payload.get("transcript_path")}
    event_id = uuid.uuid4().hex
    context_hash = write_evidence(args.context_dir, event_id, context, args.dry_run)
    worker_run_id = "codex:" + stable_id(session)
    event = {"event_id": event_id, "source": "runpod_agent",
             "worker_run_id": worker_run_id, "kind": "safety.flag",
             "rule_id": "codex.permission_request", "rule_version": "codex-hook/v1",
             "action": "approval_requested", "reason_code": "tool_requires_approval",
             "evidence_sha256": context_hash,
             "session_id": stable_id(session), "turn_id": stable_id(session, turn),
             "observed_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")}
    tool_use_id = str(payload.get("tool_use_id", ""))
    if tool_use_id:
        event["trigger_event_id"] = stable_id(session, turn, tool_use_id)
    post(event, args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=os.environ.get("CONDUCTOR_ENDPOINT", ""))
    parser.add_argument("--project", default=os.environ.get("CONDUCTOR_PROJECT", ""))
    parser.add_argument("--token-file", default=os.environ.get("CONDUCTOR_TOKEN_FILE", ""))
    parser.add_argument("--ca-file", default=os.environ.get("CONDUCTOR_CA_FILE", ""))
    parser.add_argument("--context-dir", default=os.environ.get("CONDUCTOR_SAFETY_CONTEXT_DIR", "~/.conductor/safety-context"))
    parser.add_argument("--source-revision", default="")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    s3 = sub.add_parser("s3-slots", help="read S3 slot records and post observations once")
    s3.add_argument("--bucket", required=True)
    s3.add_argument("--prefix", default="")
    dynamo = sub.add_parser("dynamodb-slots", help="read DynamoDB slot records and post observations once")
    dynamo.add_argument("--table", required=True)
    sub.add_parser("codex-hook", help="read one Codex hook event on stdin")
    args = parser.parse_args()
    if args.command == "codex-hook":
        # Hook failures never change the pending permission decision.
        try:
            codex_hook(json.load(sys.stdin), args)
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
            print("Conductor safety observation failed: %s" % type(error).__name__, file=sys.stderr)
        return
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    if args.command == "s3-slots":
        source = "s3:" + args.bucket + "/" + args.prefix.strip("/")
        slots = s3_slots(args.bucket, args.prefix)
    else:
        source = "dynamodb:" + args.table
        slots = dynamo_slots(args.table)
    scope = stable_id(source)[:12]
    for item in slots:
        for event in slot_observations(item, scope, now, args.source_revision):
            evidence = {"record_source": source, "slot_record": item}
            event["evidence_sha256"] = write_evidence(
                args.context_dir, event["event_id"], evidence, args.dry_run)
            post(event, args)


if __name__ == "__main__":
    main()
