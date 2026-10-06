#!/usr/bin/env python3
"""Materialize every factor base of a sweep as point shards, for permanent offsite storage.

    python3 sweep_points.py points NAME --write-index         # regenerate, record digests in git
    python3 sweep_points.py points NAME --check [--upload]    # regenerate, compare digests, upload
    python3 sweep_points.py points NAME --check --out DIR     # also write the shards locally
    python3 sweep_points.py read FILE                         # decode one shard (header + counts)

The sweep manifests (`sweeps.py`) are recipes. This module turns each recipe into the
bases themselves: one shard per curve, `<label>.bin.gz`, holding for every family the
members of the base at that family's largest dimension kmax. The base at dimension k is
the prefix of records with c < 2^k (V_k = span of the first k basis vectors).

Shard format `fbsweep-points/1`, gzip of:
  line 1    canonical JSON header: schema, sweep, curve label, curve ID, b, field modulus,
            families [{name, kmax, count}], record layout
  then      for each family in header order, `count` records of
            uint32 little-endian c, then x as ceil(n/8) bytes little-endian,
            sorted by c, where x = XOR of basis[i] over the bits i of c

A record is the abscissa x of the rational points of y^2 + xy = x^3 + b over it: x = 0
(c = 0) gives the single point (0, b^(1/2)), every other x the two points (x, y) and
(x, x + y), y = x * HalfTrace(x + b/x^2). So the x list is the exact point set.

`sweeps/<name>.points.csv` (in git) records each shard's x count, uncompressed length and
content SHA-256. --check regenerates every shard and fails on any difference; it also
compares every recorded experiment count (`sweeps.BUILDERS`) with the shard. --upload
puts each shard at s3://<IC_ARCHIVE_S3_URI>/factor-base-sweeps/<name>/points/<label>.bin.gz
with its content SHA-256 as metadata, skipping objects already there with that digest.
The bucket is meant to have versioning and Object Lock in compliance mode (README).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sweeps  # noqa: E402
from toycurve import canonical  # noqa: E402

SCHEMA = "fbsweep-points/1"
FIELDS = ["label", "curve_id", "x_count", "bytes", "content_sha256"]
RECORD = "uint32 little-endian c, then x as ceil(n/8) bytes little-endian; sorted by c"

_DOC: dict = {}
_CTR = None


def index_path(name: str) -> Path:
    return sweeps.DIR / f"{name}.points.csv"


def members(ctr: sweeps.Counter, b: int, basis, kmax: int) -> list[int]:
    """c in [0, 2^kmax) whose x = span index c is the abscissa of a rational point (c = 0 always)."""
    xs, ws, trx = ctr.span(tuple(basis[:kmax]), kmax)
    lb = 0
    for j in range(ctr.n):
        lb |= ((b & (ctr.T >> j)).bit_count() & 1) << j
    return [0] + [c for c in range(1, 1 << kmax) if trx[c] == (ws[c] & lb).bit_count() & 1]


def shard(doc: dict, curve: dict, ctr: sweeps.Counter) -> tuple[bytes, dict]:
    """(uncompressed shard content, {family: {k: nonzero x count}})."""
    n = doc["field"]["degree"]
    nb = (n + 7) // 8
    fams, body, counts = [], [], {}
    for name, fam in doc["families"].items():
        kmax = max(fam["dimensions"])
        cs = members(ctr, curve["b"], fam["basis"], kmax)
        xs = ctr.span(tuple(fam["basis"][:kmax]), kmax)[0]
        fams.append({"name": name, "kmax": kmax, "count": len(cs)})
        body.append(b"".join(c.to_bytes(4, "little") + xs[c].to_bytes(nb, "little") for c in cs))
        counts[name] = {k: sum(1 for c in cs if 0 < c < (1 << k)) for k in fam["dimensions"]}
    header = {"schema": SCHEMA, "sweep": doc["name"], "label": curve["label"], "curve_id": curve["curve_id"],
              "b": curve["b"], "field": doc["field"], "families": fams, "record": RECORD,
              "points": "x = 0 is the point (0, b^(1/2)); every other x carries (x, y) and (x, x + y)"}
    return canonical(header).encode() + b"\n" + b"".join(body), counts


def decode(content: bytes) -> tuple[dict, dict]:
    """(header, {family: [(c, x), ...]}) from uncompressed shard content."""
    head, _, body = content.partition(b"\n")
    header = json.loads(head)
    nb = (header["field"]["degree"] + 7) // 8
    size, pos, out = 4 + nb, 0, {}
    for fam in header["families"]:
        recs = []
        for _ in range(fam["count"]):
            recs.append((int.from_bytes(body[pos:pos + 4], "little"),
                         int.from_bytes(body[pos + 4:pos + size], "little")))
            pos += size
        out[fam["name"]] = recs
    if pos != len(body):
        raise ValueError("trailing bytes in shard")
    return header, out


def _init(name: str) -> None:
    global _DOC, _CTR
    _DOC = sweeps.load(name)
    _CTR = sweeps.Counter(_DOC["field"]["degree"], sum(1 << e for e in _DOC["field"]["modulus_exponents"]))


def _work(i: int):
    curve = _DOC["curves"][i]
    content, counts = shard(_DOC, curve, _CTR)
    return curve["label"], curve["curve_id"], content, counts


# ------------------------------------------------------------------ upload
def uploader(name: str):
    """A function (label, gz_bytes, content_sha256) -> bool uploaded, or raise if S3 is unavailable."""
    import fbarchive

    target = fbarchive.s3_target()
    if target is None:
        raise SystemExit("IC_ARCHIVE_S3_URI is not set")
    bucket, prefix = target
    base = f"{prefix}/factor-base-sweeps/{name}/points" if prefix else f"factor-base-sweeps/{name}/points"
    kind, client = fbarchive.s3_client()
    if kind is None:
        raise SystemExit(client)

    def put(label: str, blob: bytes, digest: str) -> bool:
        key = f"{base}/{label}.bin.gz"
        meta = {"content-sha256": digest, "schema": SCHEMA}
        if kind == "boto3":
            try:
                if client.head_object(Bucket=bucket, Key=key).get("Metadata", {}).get("content-sha256") == digest:
                    return False
            except Exception:  # noqa: BLE001 - absent object
                pass
            client.put_object(Bucket=bucket, Key=key, Body=blob, Metadata=meta)
            return True
        with tempfile.NamedTemporaryFile(suffix=".bin.gz") as fh:
            fh.write(blob)
            fh.flush()
            subprocess.run(["aws", "s3", "cp", fh.name, f"s3://{bucket}/{key}", "--only-show-errors",
                            "--metadata", ",".join(f"{k}={v}" for k, v in meta.items())], check=True)
        return True

    return put


# ------------------------------------------------------------------ CLI
def run_points(name: str, write_index: bool, check: bool, out: Path | None, upload: bool, workers: int,
               limit: int | None) -> int:
    doc = sweeps.load(name)
    _, recorded = sweeps.BUILDERS[name]
    rec = recorded()
    want = {}
    if check:
        with open(index_path(name), newline="") as fh:
            want = {r["label"]: r for r in csv.DictReader(fh)}
    put = uploader(name) if upload else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    rows, errors, uploaded = [], [], 0
    idx = range(len(doc["curves"]) if limit is None else min(limit, len(doc["curves"])))
    with Pool(workers, initializer=_init, initargs=(name,)) as pool:
        for label, cid, content, counts in pool.imap(_work, idx, chunksize=4):
            digest = hashlib.sha256(content).hexdigest()
            x_count = sum(len(v) for v in decode(content)[1].values())
            row = {"label": label, "curve_id": cid, "x_count": x_count, "bytes": len(content),
                   "content_sha256": digest}
            rows.append(row)
            for fam, ks in counts.items():
                for k, v in ks.items():
                    if (label, fam, k) in rec and rec[(label, fam, k)] != v:
                        errors.append(f"{label} {fam} k={k}: shard has {v} x, experiment recorded "
                                      f"{rec[(label, fam, k)]}")
            if check:
                w = want.get(label)
                if w is None or {k: str(v) for k, v in row.items()} != w:
                    errors.append(f"{label}: shard differs from {index_path(name).name}")
                    continue
            if out or put:
                blob = gzip.compress(content, compresslevel=6, mtime=0)
                if out:
                    (out / f"{label}.bin.gz").write_bytes(blob)
                if put:
                    uploaded += put(label, blob, digest)
    if check and limit is None and len(rows) != len(want):
        errors.append(f"{len(want) - len(rows)} indexed shards were not regenerated")
    if write_index:
        if limit is not None:
            raise SystemExit("--write-index needs every curve (no --limit)")
        with open(index_path(name), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    for err in errors[:20]:
        print(err)
    total = sum(r["bytes"] for r in rows)
    print(f"{name}: {len(rows)} shards, {sum(r['x_count'] for r in rows)} x values, {total / 1e9:.2f} GB "
          f"uncompressed, {uploaded} uploaded, {len(errors)} problems")
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("points")
    p.add_argument("name", choices=list(sweeps.BUILDERS))
    p.add_argument("--write-index", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--out", type=Path)
    p.add_argument("--upload", action="store_true", help="put each shard in S3 ($IC_ARCHIVE_S3_URI)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit", type=int, help="first N curves only (testing)")
    r = sub.add_parser("read")
    r.add_argument("file", type=Path)
    args = ap.parse_args()
    if args.cmd == "read":
        header, fams = decode(gzip.decompress(args.file.read_bytes()))
        print(json.dumps({**header, "records": {k: len(v) for k, v in fams.items()}}, indent=1))
        return 0
    if args.upload and not args.check:
        ap.error("--upload needs --check")
    return run_points(args.name, args.write_index, args.check, args.out, args.upload, args.workers, args.limit)


if __name__ == "__main__":
    sys.exit(main())
