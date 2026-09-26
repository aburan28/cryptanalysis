#!/usr/bin/env python3
"""One worker entry point for local containers, Modal and Runpod."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "aws"))
from worker import Worker, S3Store
from rds_gpu import Store


class ConfigurationError(ValueError):
    """A configuration diagnostic safe to print in provider logs."""


def validate_config(config, manifest):
    """Do not resume a campaign with an incompatible container build."""
    for name in ("curve", "batch", "blockThreads", "minBlocks", "packed",
                 "walkId", "checkpointVersion", "recordFormat"):
        if config.get(name) != manifest.get(name):
            raise ConfigurationError(f"campaign {name}={config.get(name)!r} does not match container {manifest.get(name)!r}")
    for name in ("workers", "steps", "checkpointEvery", "uploadEvery"):
        value = config.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigurationError(f"campaign {name} must be a positive integer")
    if config["workers"] % config["blockThreads"]:
        raise ConfigurationError("workers must be a multiple of blockThreads")
    weight = config.get("dpWeight")
    if isinstance(weight, bool) or not isinstance(weight, int) or not 0 <= weight <= 131:
        raise ConfigurationError("dpWeight must be an integer from 0 to 131")
    if "dpWeight" in manifest and weight != manifest["dpWeight"]:
        raise ConfigurationError("campaign dpWeight does not match the production profile")
    if config.get("campaignId") == "ecc2k-130" and (
            weight != 32 or config.get("walkId") != "certicom-ecc2k130-frobenius-v1"):
        raise ConfigurationError("ecc2k-130 requires the legacy Frobenius walk at DP weight 32")
    if config.get("extraArgs"):
        raise ConfigurationError("cloud campaigns must not override client arguments with extraArgs")
    base = config.get("runIdBase", 1)
    if isinstance(base, bool) or not isinstance(base, int) or not 1 <= base <= 65535:
        raise ConfigurationError("runIdBase must be an integer from 1 to 65535")


def initialize_campaign(worker):
    """Create only a missing configuration in the isolated production prefix."""
    if not os.environ.get("ECC_PREFIX"):
        return
    template = ROOT / "aws" / "campaign.json"
    manifest = json.loads((ROOT / "build.json").read_text())
    config = json.loads(template.read_text())
    validate_config(config, manifest)
    worker.store.create(str(template), "campaign.json")


def preflight(worker, *, s3_only=False, check_client=True):
    worker.loadConfig()
    manifest_path = Path(os.environ.get("ECC_BUILD_MANIFEST", ROOT / "build.json"))
    if not manifest_path.is_file():
        raise ConfigurationError("build manifest missing; use the runner container image")
    manifest = json.loads(manifest_path.read_text())
    validate_config(worker.cfg, manifest)
    if worker.cfg.get("campaignId") == "ecc2k-130" and isinstance(worker.store, S3Store):
        # The historical RDS row has no walk identity. Bind this compatibility
        # decision to the actual legacy S3 configuration verified on the GPU.
        path = Path(worker.work) / "legacy-campaign.json"
        shared = S3Store(worker.store.bucket)
        if not shared.get("campaign.json", str(path)):
            raise ConfigurationError("the shared legacy campaign configuration is missing")
        legacy = json.loads(path.read_text())
        if (legacy.get("curve") != 131 or legacy.get("packed") is not True
                or legacy.get("dpWeight") != 32
                or legacy.get("binarySha256") != manifest.get("legacyBinarySha256")):
            raise ConfigurationError("shared legacy campaign changed; repeat the compatibility check")
    if check_client and (not Path(worker.client).is_file() or not os.access(worker.client, os.X_OK)):
        raise ConfigurationError("ECC_CLIENT is not an executable file")
    if not s3_only:
        try:
            store = Store()
        except Exception as exc:
            detail = str(exc).lower()
            if "no password supplied" in detail:
                message = "RDS requires a password; set PGPASSWORD or include it in RHO_DP_DSN"
            elif "password authentication failed" in detail:
                message = "RDS rejected the database username/password"
            elif "timeout" in detail:
                message = "RDS connection timed out; check endpoint routing and security-group access"
            elif "certificate" in detail or "sslrootcert" in detail:
                message = "RDS TLS certificate verification failed; check PGSSLROOTCERT and the endpoint hostname"
            else:
                message = "RDS connection failed (%s); check the database connection configuration" % type(exc).__name__
            raise ConfigurationError(message) from None
        try:
            with store._conn.cursor() as cur:
                cur.execute("SELECT to_regclass('rho_campaigns'), EXISTS "
                            "(SELECT 1 FROM pg_proc WHERE proname = 'report_dp' "
                            "AND pg_function_is_visible(oid))")
                table, function = cur.fetchone()
                if table is None or not function:
                    raise ConfigurationError("RDS requires the existing rho_campaigns table and report_dp function")
            if worker.cfg.get("campaignId") == "ecc2k-130":
                store.register("ecc2k-130", dp_weight=worker.cfg["dpWeight"], walk_id=worker.cfg["walkId"])
        finally:
            store.close()
    return manifest


def smoke(worker, *, s3_only=False):
    """Bounded round trip: one S3 object, rolled-back RDS reports; no GPU job."""
    token = uuid.uuid4().hex
    key = f"checks/{token}/dp.bin"
    blob = struct.pack("<4Q", 1, 11, 22, 33)
    src = Path(worker.work) / "smoke.bin"
    dst = Path(worker.work) / "smoke.download"
    src.write_bytes(blob)
    try:
        worker.store.put(str(src), key)
        if not worker.store.get(key, str(dst)) or dst.read_bytes() != blob:
            raise RuntimeError("S3 round-trip bytes differ")
        if not s3_only:
            store = Store()
            try:
                # Nothing survives in RDS, including the synthetic campaign.
                # Sequence values can advance even though rows roll back.
                with store._conn.transaction(force_rollback=True):
                    campaign = f"ecc2k130-check-{token}"
                    store.register(campaign, dp_weight=worker.cfg["dpWeight"], walk_id=worker.cfg.get("walkId"))
                    pk = blob[8:]
                    first, duplicate, collision = store.report_many(
                        [(pk, 1), (pk, 1), (pk, 2)], campaign=campaign, worker_id="smoke")
                    if not first["is_new"] or duplicate["is_new"] or duplicate["is_collision"]:
                        raise RuntimeError("RDS report_dp is not idempotent for duplicate records")
                    if not collision["is_collision"]:
                        raise RuntimeError("RDS did not detect a same-key/different-seed collision")
            finally:
                store.close()
    finally:
        # Keep the small S3 check artifact for diagnosis; no delete permission
        # is needed. A bucket lifecycle rule can expire checks/ after a day.
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)
    return {"s3_key": key, "rds": "skipped" if s3_only else "round-trip rolled back"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "smoke", "run"))
    parser.add_argument("--seconds", type=int, default=3600,
                        help="run duration before graceful shutdown (1..82800)")
    parser.add_argument("--s3-only", action="store_true", help="explicitly disable direct RDS reporting")
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 82800:
        parser.error("--seconds must be between 1 and 82800")
    os.environ.setdefault("ECC_ROOT", "/workspace/ecc2k130")
    os.environ.setdefault("ECC_CLIENT", str(ROOT / "ecc2k130"))
    os.environ["ECC_RUN_SECONDS"] = str(args.seconds)
    if args.s3_only:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("RHO_DP_DSN", None)
    if not os.environ.get("ECC_LOCAL_STORE") and not os.environ.get("ECC_BUCKET"):
        raise ConfigurationError("set ECC_BUCKET to the campaign bucket")
    if not args.s3_only and not (os.environ.get("RHO_DP_DSN") or os.environ.get("DATABASE_URL")):
        raise ConfigurationError("set RHO_DP_DSN or DATABASE_URL, or explicitly select --s3-only")
    worker = Worker()
    if args.command == "run":
        initialize_campaign(worker)
    preflight(worker, s3_only=args.s3_only)
    if args.command == "preflight":
        print(json.dumps({"ok": True, "preflight": True, "rds": not args.s3_only}))
        return 0
    if args.command == "smoke":
        print(json.dumps({"ok": True, **smoke(worker, s3_only=args.s3_only)}))
        return 0
    return worker.run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigurationError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        # DSNs and driver diagnostics must not enter provider logs.
        print(f"cloud runner failed ({type(exc).__name__}); check S3/RDS access and campaign configuration",
              file=sys.stderr)
        raise SystemExit(1)
