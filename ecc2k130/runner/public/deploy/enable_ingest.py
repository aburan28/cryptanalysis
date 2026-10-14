#!/usr/bin/env python3
"""Prepare the RDS ingester on the gateway host, then optionally start it.

Only run after the public gateway is healthy and its S3 registration has been
checked. The existing RDS secret stays on the host; this script prints no DSN.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import quote, urlencode
from urllib.request import urlopen

PUBLIC = Path(__file__).resolve().parents[1]
CA_URL = "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"


def dsn(secret: dict, host: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+\.[a-z0-9-]+\.us-west-2\.rds\.amazonaws\.com", host):
        raise ValueError("expected a us-west-2 RDS endpoint")
    database = secret["dbname"]
    if not re.fullmatch(r"[a-zA-Z0-9_]+", database):
        raise ValueError("RDS database name has an unexpected format")
    user = quote(secret["username"], safe="")
    password = quote(secret["password"], safe="")
    options = urlencode({"sslmode": "verify-full",
                         "sslrootcert": "/opt/ecc2k130/rds-ca.pem"})
    return f"postgresql://{user}:{password}@{host}:5432/{database}?{options}"


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", required=True)
    parser.add_argument("--secret-id", default="rho/dp-rds")
    parser.add_argument("--start", action="store_true",
                        help="start the ingester after its read-only contract check")
    args = parser.parse_args(argv)
    try:
        response = subprocess.run(["aws", "secretsmanager", "get-secret-value",
                                   "--secret-id", args.secret_id, "--query", "SecretString",
                                   "--output", "text"], capture_output=True, text=True, check=True)
        credentials = json.loads(response.stdout)
        connection = dsn(credentials, args.db_host)
        with urlopen(CA_URL, timeout=30) as source:
            bundle = source.read(256 * 1024 + 1)
        if not (bundle.startswith(b"-----BEGIN CERTIFICATE-----")
                and b"-----END CERTIFICATE-----" in bundle and len(bundle) <= 256 * 1024):
            raise RuntimeError("RDS CA bundle has an unexpected format")
        atomic_write(PUBLIC / "deploy/rds-ca.pem", bundle, 0o644)
        env_file = PUBLIC / ".env"
        existing = env_file.read_text().splitlines() if env_file.is_file() else []
        lines = [line for line in existing if not line.startswith("RHO_DP_DSN=")]
        lines.append("RHO_DP_DSN=" + connection)
        atomic_write(env_file, ("\n".join(lines) + "\n").encode(), 0o600)
        check = ["docker", "compose", "--profile", "live-ingest", "run", "--rm",
                 "--no-deps", "ingest", "python3", "/opt/ecc2k130/public/check_rds.py"]
        subprocess.run(check, cwd=PUBLIC, check=True)
        if args.start:
            subprocess.run(["docker", "compose", "--profile", "live-ingest",
                            "up", "-d", "ingest"], cwd=PUBLIC, check=True)
    except Exception as exc:
        # subprocess stderr, URLs, and connection strings may hold credentials.
        raise SystemExit(f"ingest setup stopped ({type(exc).__name__}); inspect privately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
