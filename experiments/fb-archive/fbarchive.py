#!/usr/bin/env python3
"""Archive factor bases: canonical record plus enumerated usable points, compressed and indexed.

    python3 fbarchive.py export --n 19 --family geomtrace --l 5          # one base
    python3 fbarchive.py export-suite --suite full                       # every ic-bench base
    python3 fbarchive.py export --n 131 --family geomtrace --l 12        # ECC2K-130, pure Python
    python3 fbarchive.py export --n 131 --family geomtraceu --l 24 --no-points   # recipe only
    python3 fbarchive.py verify [--rebuild]                              # check every index row
    python3 fbarchive.py upload [--dry-run] [--require]                  # to $IC_ARCHIVE_S3_URI

One archive is `<family>-l<l>-s<seed>-<digest12>.json.gz` under bases/<curve-id>/: a
deterministic gzip (mtime 0) of canonical JSON holding the AGENTS.md `factor_base`
record, its SHA-256, the exact `field` and `curve` records, and the sorted usable points
[[x, y], ...] whose SHA-256 is the record's `enumerated_set_sha256`.  index.csv lists
every archive with its digests, counts, byte size and the SHA-256 of the compressed file.
Archives up to --max-git-bytes are committed; larger ones go to large/ (ignored by git)
with storage `s3` and must be uploaded.  Nothing here reads or writes credentials.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import lzma
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))

from toycurve import canonical, sha256_hex  # noqa: E402

SCHEMA = "ic-factor-base-archive/1"
INDEX = HERE / "index.csv"
INDEX_FIELDS = ["factor_base_sha256", "curve_id", "n", "family", "l", "seed", "fb_points", "geometric_points",
                "effective_columns", "strict_points", "quotient_rule", "points_included", "path", "storage",
                "bytes", "file_sha256", "content_sha256", "enumerated_set_sha256"]
MAX_GIT_BYTES = 1 << 20
TOY_MAX_N = 63


# ------------------------------------------------------------------ building
def toy_archive(n: int, family: str, l: int, seed: int, points: bool) -> dict:
    from factor_base import FactorBase
    from toycurve import ToyCurve

    C = ToyCurve(n)
    fb = FactorBase(C, family, l, seed)
    rec = fb.record()
    usable = sorted([int(x), int(y), i] for i, (x, y, u) in enumerate(zip(fb.xs, fb.ys, fb.usable)) if u)
    doc = {
        "field": C.field_record(),
        "curve": {**C.curve_record(), "curve_id": C.curve_id},
        "factor_base": rec,
        "points": [[x, y] for x, y, _ in usable] if points else None,
        "point_columns": [[int(fb.col_of[i]), int(fb.col_coeff[i]) % C.r] for _, _, i in usable] if points else None,
        "column_representatives": [list(p) for p in fb.column_reps] if points else None,
        "builder": "pdp-degree-heuristics/factor_base.py FactorBase (pdpkernel.c)",
    }
    return doc


def big_factor_base(n: int, family: str, l: int, seed: int, points: bool, strict_limit: int) -> dict:
    from purepy import PyKoblitz

    if n != 131:
        raise ValueError("beyond n = 63 only the ECC2K-130 field (n = 131) has a fixed generator here")
    return py_factor_base(PyKoblitz.ecc2k130(), family, l, seed, points, strict_limit)


def py_factor_base(C, family: str, l: int, seed: int, points: bool, strict_limit: int) -> dict:
    """The same record as FactorBase.record(), built in pure Python on a purepy.PyKoblitz curve."""
    import factor_base as fbmod
    from purepy import INF

    basis, params = fbmod.family_basis(C, family, l, seed)
    K = C.K
    frob_stable = fbmod.rank(basis + [K.sqr(v) for v in basis]) == l
    rec_points = pts = cols = strict = None
    geometric = usable_n = None
    if points:
        pts = []
        for x in _span(basis):
            P = C.lift(int(x))
            if P is not None:
                pts.append(P)
                if P[0]:
                    pts.append(C.neg(P))
        geometric = len(pts)
        torsion = C.cofactor_torsion()
        tors = set(torsion)
        usable = sorted(P for P in pts if P not in tors)
        usable_n = len(usable)
        if frob_stable:
            raise ValueError("Frobenius-stable subspaces need the tau-orbit column rule; not implemented at n = 131")
        # columns are the +- classes of pi_r(P): P ~ +-P + T for T in E[h]
        cols = len({min(C.add(P, T)[0] for T in torsion) for P in usable})
        if len(usable) <= strict_limit:
            strict = sum(1 for P in usable if C.smul(P, C.r) is INF)
        rec_points = [[x, y] for x, y in usable]
    rec = {
        "curve_id": C.curve_id,
        "construction": {
            "family": family,
            "basis": [int(b) for b in basis],
            "params": {k: int(v) for k, v in params.items()},
            "polynomial_constraint": "none",
            "shifted_bases": "none",
        },
        "subgroup_policy": "cofactor_projection",
        "enumerated_set_sha256": sha256_hex(rec_points) if points else None,
        "nominal_dimension": l,
        "geometric_point_count": geometric,
        "actual_usable_point_count": usable_n,
        "strict_subgroup_point_count": strict,
        "quotient_rule": "sign+frobenius" if frob_stable else "sign",
        "effective_columns": cols,
    }
    return {
        "field": C.field_record(),
        "curve": {**C.curve_record(), "curve_id": C.curve_id},
        "factor_base": rec,
        "points": rec_points,
        "point_columns": None,
        "column_representatives": None,
        "builder": "fb-archive/purepy.py with factor_base.family_basis"
        + ("" if points else "; points not enumerated, so B and the column count are unknown (null)"),
        "strict_limit": strict_limit,
    }


def _span(basis: list[int]):
    out = [0]
    for b in basis:
        out += [v ^ b for v in out]
    return out


def build(n: int, family: str, l: int, seed: int, points: bool = True, strict_limit: int = 10_000) -> dict:
    doc = toy_archive(n, family, l, seed, points) if n <= TOY_MAX_N else big_factor_base(n, family, l, seed, points, strict_limit)
    doc = {"schema": SCHEMA, **doc, "factor_base_sha256": sha256_hex(doc["factor_base"]),
           "points_encoding": "[x, y] unsigned integers in the field's element encoding, sorted",
           "recipe": {"n": n, "family": family, "l": l, "seed": seed}}
    return doc


# ------------------------------------------------------------------ files and index
def compress(data: bytes, codec: str) -> bytes:
    if codec == "gz":
        return gzip.compress(data, compresslevel=9, mtime=0)
    if codec == "xz":
        return lzma.compress(data, preset=9)
    raise ValueError(codec)


def decompress(path: Path) -> bytes:
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else lzma.decompress(raw)


def read_index() -> list[dict]:
    if not INDEX.exists():
        return []
    with INDEX.open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_index(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: (int(r["n"]), r["curve_id"], r["family"], int(r["l"]), int(r["seed"]),
                                       r["factor_base_sha256"]))
    with INDEX.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=INDEX_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def store(doc: dict, codec: str = "gz", max_git_bytes: int = MAX_GIT_BYTES) -> dict:
    content = canonical(doc).encode()
    blob = compress(content, codec)
    rec, recipe = doc["factor_base"], doc["recipe"]
    name = f"{recipe['family']}-l{recipe['l']}-s{recipe['seed']}-{doc['factor_base_sha256'][:12]}.json.{codec}"
    storage = "git" if len(blob) <= max_git_bytes else "s3"
    rel = Path("bases" if storage == "git" else "large") / rec["curve_id"] / name
    path = HERE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    row = {
        "factor_base_sha256": doc["factor_base_sha256"], "curve_id": rec["curve_id"], "n": recipe["n"],
        "family": recipe["family"], "l": recipe["l"], "seed": recipe["seed"],
        "fb_points": rec["actual_usable_point_count"], "geometric_points": rec["geometric_point_count"],
        "effective_columns": rec["effective_columns"], "strict_points": rec["strict_subgroup_point_count"],
        "quotient_rule": rec["quotient_rule"], "points_included": doc["points"] is not None,
        "path": str(rel), "storage": storage, "bytes": len(blob),
        "file_sha256": hashlib.sha256(blob).hexdigest(), "content_sha256": hashlib.sha256(content).hexdigest(),
        "enumerated_set_sha256": rec["enumerated_set_sha256"],
    }
    row = {k: ("" if v is None else v) for k, v in row.items()}
    rows = [r for r in read_index() if r["path"] != row["path"]]
    write_index(rows + [row])
    return row


# ------------------------------------------------------------------ verification
def verify_row(row: dict, rebuild: bool, rebuild_max_points: int) -> list[str]:
    errors = []
    path = HERE / row["path"]
    if not path.exists():
        return [] if row["storage"] == "s3" else [f"{row['path']}: missing"]
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != row["file_sha256"]:
        errors.append(f"{row['path']}: file SHA-256 differs from the index")
    content = decompress(path)
    if hashlib.sha256(content).hexdigest() != row["content_sha256"]:
        errors.append(f"{row['path']}: content SHA-256 differs from the index")
    doc = json.loads(content)
    rec = doc["factor_base"]
    if sha256_hex(rec) != doc["factor_base_sha256"] or doc["factor_base_sha256"] != row["factor_base_sha256"]:
        errors.append(f"{row['path']}: factor_base record digest mismatch")
    if doc["points"] is not None:
        if sha256_hex(doc["points"]) != rec["enumerated_set_sha256"]:
            errors.append(f"{row['path']}: enumerated_set_sha256 does not match the points")
        if len(doc["points"]) != rec["actual_usable_point_count"]:
            errors.append(f"{row['path']}: point count differs from B")
    if rebuild and (doc["points"] is None or len(doc["points"]) <= rebuild_max_points):
        rc = doc["recipe"]
        again = build(rc["n"], rc["family"], rc["l"], rc["seed"], doc["points"] is not None,
                      doc.get("strict_limit", 10_000))
        if canonical(again).encode() != content:
            errors.append(f"{row['path']}: rebuilding from the recipe gives different content")
    return errors


# ------------------------------------------------------------------ S3
def s3_target() -> tuple[str, str] | None:
    uri = os.environ.get("IC_ARCHIVE_S3_URI", "").strip()
    if not uri:
        return None
    if not uri.startswith("s3://"):
        raise ValueError("IC_ARCHIVE_S3_URI must look like s3://bucket/prefix")
    bucket, _, prefix = uri[5:].partition("/")
    return bucket, prefix.strip("/")


def s3_client():
    """(kind, handle) for boto3 or the aws CLI, or (None, reason) when neither can authenticate."""
    try:
        import boto3  # type: ignore

        session = boto3.Session()
        if session.get_credentials() is None:
            return None, "boto3 found no AWS credentials"
        return "boto3", session.client("s3")
    except ImportError:
        pass
    if shutil.which("aws") is None:
        return None, "neither boto3 nor the aws CLI is installed"
    probe = subprocess.run(["aws", "sts", "get-caller-identity"], capture_output=True, text=True)
    if probe.returncode != 0:
        return None, "the aws CLI found no usable credentials"
    return "cli", None


def upload(dry_run: bool, require: bool) -> int:
    target = s3_target()
    rows = read_index()
    if target is None:
        msg = "IC_ARCHIVE_S3_URI is not set; skipping the S3 upload"
        print(msg, file=sys.stderr)
        return 1 if require else 0
    bucket, prefix = target
    base = f"{prefix}/factor-bases" if prefix else "factor-bases"
    plan = [(HERE / r["path"], f"{base}/{r['curve_id']}/{Path(r['path']).name}", r) for r in rows
            if (HERE / r["path"]).exists()]
    plan.append((INDEX, f"{base}/index.csv", None))
    if dry_run:
        for path, key, _ in plan:
            print(f"would upload {path.relative_to(HERE)} -> s3://{bucket}/{key}")
        return 0
    kind, client = s3_client()
    if kind is None:
        print(f"{client}; skipping the S3 upload", file=sys.stderr)
        return 1 if require else 0
    done = 0
    for path, key, row in plan:
        meta = {} if row is None else {"sha256": row["file_sha256"], "factor-base-sha256": row["factor_base_sha256"]}
        if kind == "boto3":
            if row is not None:
                try:
                    head = client.head_object(Bucket=bucket, Key=key)
                    if head.get("Metadata", {}).get("sha256") == row["file_sha256"]:
                        continue
                except Exception:  # noqa: BLE001 - absent object
                    pass
            client.upload_file(str(path), bucket, key, ExtraArgs={"Metadata": meta})
        else:
            cmd = ["aws", "s3", "cp", str(path), f"s3://{bucket}/{key}", "--only-show-errors"]
            if meta:
                cmd += ["--metadata", ",".join(f"{k}={v}" for k, v in meta.items())]
            subprocess.run(cmd, check=True)
        done += 1
    print(f"uploaded {done} of {len(plan)} objects to s3://{bucket}/{base}/ ({kind})")
    return 0


# ------------------------------------------------------------------ CLI
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="archive one factor base")
    e.add_argument("--n", type=int, required=True)
    e.add_argument("--family", required=True)
    e.add_argument("--l", type=int, required=True)
    e.add_argument("--seed", type=int, default=1)
    e.add_argument("--no-points", action="store_true", help="record the recipe and basis only (B stays null)")
    e.add_argument("--codec", default="gz", choices=["gz", "xz"])
    e.add_argument("--strict-limit", type=int, default=10_000, help="n = 131: count [r]P = O only up to this many points")
    e.add_argument("--max-git-bytes", type=int, default=MAX_GIT_BYTES)
    s = sub.add_parser("export-suite", help="archive every factor base of an ic-bench suite")
    s.add_argument("--suite", default="full")
    v = sub.add_parser("verify", help="check every archive against the index")
    v.add_argument("--rebuild", action="store_true", help="also rebuild each base from its recipe")
    v.add_argument("--rebuild-max-points", type=int, default=20_000)
    u = sub.add_parser("upload", help="upload the archives and index to $IC_ARCHIVE_S3_URI")
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--require", action="store_true", help="fail instead of skipping when S3 is unavailable")
    args = ap.parse_args()
    if args.cmd == "export":
        doc = build(args.n, args.family, args.l, args.seed, not args.no_points, args.strict_limit)
        row = store(doc, args.codec, args.max_git_bytes)
        print(json.dumps(row))
    elif args.cmd == "export-suite":
        sys.path.insert(0, str(HERE.parent / "ic-bench"))
        from bench import SUITES

        seen = set()
        for c in SUITES[args.suite]:
            key = (c["n"], c["family"], c["l"], c["seed"])
            if key not in seen:
                seen.add(key)
                row = store(build(*key))
                print(f"{row['path']}  B={row['fb_points']} columns={row['effective_columns']} {row['bytes']} bytes")
    elif args.cmd == "verify":
        rows = read_index()
        errors = [err for r in rows for err in verify_row(r, args.rebuild, args.rebuild_max_points)]
        on_disk = {str(p.relative_to(HERE)) for p in (HERE / "bases").rglob("*.json.*")}
        errors += [f"{p}: not in index.csv" for p in sorted(on_disk - {r["path"] for r in rows})]
        for err in errors:
            print(err)
        print(f"{len(rows)} archives, {len(errors)} problems")
        sys.exit(1 if errors else 0)
    elif args.cmd == "upload":
        sys.exit(upload(args.dry_run, args.require))


if __name__ == "__main__":
    main()
