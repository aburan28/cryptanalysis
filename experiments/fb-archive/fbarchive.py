#!/usr/bin/env python3
"""Archive factor bases: canonical record plus enumerated usable points, compressed and indexed.

    python3 fbarchive.py export --n 19 --family geomtrace --l 5          # one base
    python3 fbarchive.py export-suite --suite full                       # every ic-bench base
    python3 fbarchive.py export --n 131 --family geomtrace --l 12        # ECC2K-130, pure Python
    python3 fbarchive.py export --n 131 --family geomtraceu --l 24 --no-points   # recipe only
    python3 fbarchive.py export --n 13 --family nbweight --l 2           # weight base, l = w
    python3 fbarchive.py export --n 23 --family kerfrob --l 11 --seed 0 --extra a2=0   # external.py
    python3 fbarchive.py verify [--rebuild]                              # check every index row
    python3 fbarchive.py upload [--dry-run] [--require]                  # to $IC_ARCHIVE_S3_URI

One archive is `<family>-l<l>-s<seed>-<digest12>.json.gz` under bases/<curve-id>/: a
deterministic gzip (mtime 0) of canonical JSON holding the AGENTS.md `factor_base`
record, its SHA-256, the exact `field` and `curve` records, and the sorted usable points
[[x, y], ...] whose SHA-256 is the record's `enumerated_set_sha256`.  index.csv lists
every archive with its digests, counts, byte size and the SHA-256 of the compressed file.
aliases.csv maps digests that results cite under another convention (the Rust suite's
sorted hex lines) to the archive whose points reproduce them; `verify` recomputes each.
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
import chunked_archive  # noqa: E402

SCHEMA = "ic-factor-base-archive/1"
INDEX = HERE / "index.csv"
ALIASES = HERE / "aliases.csv"
ALIAS_FIELDS = ["cited_sha256", "convention", "factor_base_sha256", "experiment"]
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


WEIGHT_FAMILY = "nbweight"


def weight_archive(n: int, w: int, seed: int, points: bool) -> dict:
    """{P : 1 <= HW(x(P)) <= w}, the Hamming weight taken in a normal basis.

    This is the Frobenius-stable, non-linear base of ecc2k130/runner/codegen/indexcalc.py
    (--basis pb), built through the same curves.NormalView (normal element seeded by n)
    and CurvePb, so the archived point set is exactly the one indexcalc.factorBase and
    experiments/frobenius-quotient-m4/ladder.py use.  It is not a subspace, so it gets
    its own field and curve records: NormalView chooses its own modulus, which is not
    always ToyCurve's, and ToyCurve refuses n where r^2 divides #E.  `l` is w here.
    Columns are x-classes under sign and Frobenius (weight is sigma-invariant); no
    subgroup projection is applied, matching how ladder.py uses the base, so
    strict-subgroup counts are null (unknown)."""
    if seed != 1:
        raise ValueError("nbweight has no seed: NormalView is seeded by n; use --seed 1")
    if n % 2 == 0:
        raise ValueError("nbweight needs odd n (half-trace point recovery)")
    sys.path.insert(0, str(ROOT / "ecc2k130" / "runner" / "codegen"))
    import curves

    nv = curves.NormalView(n)
    E = curves.CurvePb(nv.pb)
    exps = sorted({n, 0, *[t for t in nv.taps if t >= 0]}, reverse=True)
    mod = sum(1 << e for e in exps)
    if mod != nv.poly:
        raise ValueError("NormalView modulus does not match its taps")
    field_rec = {
        "characteristic": 2,
        "degree": n,
        "representation": "polynomial_basis",
        "modulus_exponents": exps,
        "element_encoding": "unsigned integer; bit i is the coefficient of z^i",
        "normal_view": {"builder": "ecc2k130/runner/codegen/curves.py NormalView", "seed": n,
                        "tries": 400, "normal_element": nv.conj[0]},
    }
    order = curves.curveOrder(n)
    curve_rec = {
        "model": "y^2 + x*y = x^3 + a2*x^2 + a6",
        "a2": 0,
        "a6": 1,
        "order": order,
        "trace": (1 << n) + 1 - order,
        "subgroup_order": None,
        "cofactor": None,
        "generator": None,
        "target_group": "full group E(F_2^n): ladder.py draws planted and uniformly random targets",
    }
    curve_id = f"EC1N{n}Ckb1h{sha256_hex({'field': field_rec, 'curve': curve_rec})[:12]}"
    xs = []
    for k in range(1, w + 1):
        for sup in _combinations(n, k):
            c = 0
            for i in sup:
                c |= 1 << i
            xs.append(nv.fromCoords(c))
    pts = []
    for x in xs:
        P = E.pointFromX(x)
        if P is not None:
            pts.append((P[0], P[1]))
            pts.append((P[0], P[0] ^ P[1]))
    pts = sorted(set(pts))
    base_x = {x for x, _ in pts}
    seen, orbits = set(), 0
    for x in sorted(base_x):
        if x in seen:
            continue
        orbits += 1
        y = x
        for _ in range(n):
            seen.add(y)
            y = nv.pb.sqr(y)
    rec_points = [[x, y] for x, y in pts]
    rec = {
        "curve_id": curve_id,
        "construction": {
            "family": WEIGHT_FAMILY,
            "basis": None,
            "params": {"w": w, "normal_element": nv.conj[0]},
            "polynomial_constraint": "1 <= Hamming weight of the normal-basis coordinates of x <= w",
            "shifted_bases": "none",
        },
        "subgroup_policy": "none",
        "enumerated_set_sha256": sha256_hex(rec_points) if points else None,
        "nominal_dimension": None,
        "geometric_point_count": len(pts) if points else None,
        "actual_usable_point_count": len(pts) if points else None,
        "strict_subgroup_point_count": None,
        "quotient_rule": "sign+frobenius",
        "effective_columns": orbits if points else None,
        "x_classes": len(base_x) if points else None,
    }
    return {
        "field": field_rec,
        "curve": {**curve_rec, "curve_id": curve_id},
        "factor_base": rec,
        "points": rec_points if points else None,
        "point_columns": None,
        "column_representatives": None,
        "builder": "fb-archive/fbarchive.py weight_archive via codegen curves.NormalView + CurvePb",
    }


def _combinations(n: int, k: int):
    """Index subsets of size exactly k, lexicographic."""
    if k == 0:
        yield []
        return
    for first in range(n):
        for rest in _combinations_from(first + 1, n, k - 1):
            yield [first] + rest


def _combinations_from(start: int, n: int, k: int):
    if k == 0:
        yield []
        return
    for i in range(start, n):
        for rest in _combinations_from(i + 1, n, k - 1):
            yield [i] + rest


def _span(basis: list[int]):
    out = [0]
    for b in basis:
        out += [v ^ b for v in out]
    return out


def build(n: int, family: str, l: int, seed: int, points: bool = True, strict_limit: int = 10_000,
          extra: dict | None = None) -> dict:
    import external

    extra = dict(extra or {})
    if family in external.FAMILIES:
        doc = external.build(n, family, l, seed, points, extra)
    elif extra:
        raise ValueError(f"family {family} takes no extra recipe parameters")
    elif family == WEIGHT_FAMILY:
        doc = weight_archive(n, l, seed, points)
    elif n <= TOY_MAX_N:
        doc = toy_archive(n, family, l, seed, points)
    else:
        doc = big_factor_base(n, family, l, seed, points, strict_limit)
    doc = {"schema": SCHEMA, **doc, "factor_base_sha256": sha256_hex(doc["factor_base"]),
           "points_encoding": "[x, y] unsigned integers in the field's element encoding, sorted",
           "recipe": {"n": n, "family": family, "l": l, "seed": seed, **extra}}
    return doc


# ------------------------------------------------------------------ files and index
def compress(data: bytes, codec: str) -> bytes:
    if codec == "gz":
        return gzip.compress(data, compresslevel=9, mtime=0)
    if codec == "xz":
        return lzma.compress(data, preset=9)
    raise ValueError(codec)


def archive_bytes(path: Path) -> bytes:
    return chunked_archive.read(path) if path.name.endswith(chunked_archive.SUFFIX) else path.read_bytes()


def archive_paths(path: Path) -> list[Path]:
    return chunked_archive.paths(path) if path.name.endswith(chunked_archive.SUFFIX) else [path]


def decompress(path: Path, raw: bytes | None = None) -> bytes:
    if raw is None:
        raw = archive_bytes(path)
    codec = chunked_archive.metadata(path)["codec"] if path.name.endswith(chunked_archive.SUFFIX) else path.suffix[1:]
    return gzip.decompress(raw) if codec == "gz" else lzma.decompress(raw)


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


def store(doc: dict, codec: str = "gz", max_git_bytes: int = MAX_GIT_BYTES, chunk_bytes: int = 0) -> dict:
    content = canonical(doc).encode()
    blob = compress(content, codec)
    rec, recipe = doc["factor_base"], doc["recipe"]
    name = f"{recipe['family']}-l{recipe['l']}-s{recipe['seed']}-{doc['factor_base_sha256'][:12]}.json.{codec}"
    storage = "git" if len(blob) <= max_git_bytes else "s3"
    if chunk_bytes:
        if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= chunked_archive.MAX_PART:
            raise ValueError("invalid chunk byte limit")
        if storage == "s3":
            storage = "git-chunks"
            name += chunked_archive.SUFFIX
    rel = Path("large" if storage == "s3" else "bases") / rec["curve_id"] / name
    path = HERE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if storage == "git-chunks":
        chunked_archive.write(path, blob, codec, chunk_bytes)
    else:
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
    try:
        blob = archive_bytes(path)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f"{row['path']}: invalid archive parts: {error}"]
    if len(blob) != int(row["bytes"]):
        errors.append(f"{row['path']}: compressed byte count differs from the index")
    if hashlib.sha256(blob).hexdigest() != row["file_sha256"]:
        errors.append(f"{row['path']}: file SHA-256 differs from the index")
    content = decompress(path, blob)
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
        extra = {k: v for k, v in rc.items() if k not in ("n", "family", "l", "seed")}
        again = build(rc["n"], rc["family"], rc["l"], rc["seed"], doc["points"] is not None,
                      doc.get("strict_limit", 10_000), extra)
        if canonical(again).encode() != content:
            errors.append(f"{row['path']}: rebuilding from the recipe gives different content")
    return errors


def read_aliases() -> list[dict]:
    if not ALIASES.exists():
        return []
    with ALIASES.open(newline="") as fh:
        return list(csv.DictReader(fh))


def verify_aliases(rows: list[dict]) -> list[str]:
    """Each alias must point at an archive whose points give the cited digest under its convention."""
    import external

    by_digest = {r["factor_base_sha256"]: r for r in rows}
    errors = []
    for a in read_aliases():
        row = by_digest.get(a["factor_base_sha256"])
        if row is None:
            errors.append(f"aliases.csv: {a['cited_sha256'][:12]} points at an unindexed archive")
            continue
        path = HERE / row["path"]
        if not path.exists():
            continue
        doc = json.loads(decompress(path))
        if a["convention"] != external.RUST_DIGEST:
            errors.append(f"aliases.csv: unknown convention {a['convention']!r}")
        elif doc["points"] is None or external.rust_points_digest(doc["points"]) != a["cited_sha256"]:
            errors.append(f"aliases.csv: {a['cited_sha256'][:12]} is not the digest of {row['path']}")
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


def rebuild_missing(rows: list[dict]) -> list[str]:
    """Rebuild each `storage=s3` archive absent here (too large for git) from its recipe.

    The rebuilt content must match the indexed content_sha256; the compressed bytes are
    written to the row's path so the upload below can carry them. Returns the problems."""
    import external

    errors = []
    for r in rows:
        path = HERE / r["path"]
        if r["storage"] != "s3" or path.exists():
            continue
        if r["family"] in external.FAMILIES:
            errors.append(f"{r['path']}: external family; rebuild needs its extra recipe parameters")
            continue
        doc = build(int(r["n"]), r["family"], int(r["l"]), int(r["seed"]), r["points_included"] == "True")
        content = canonical(doc).encode()
        if hashlib.sha256(content).hexdigest() != r["content_sha256"]:
            errors.append(f"{r['path']}: rebuilt content differs from the index")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compress(content, "xz" if path.suffix == ".xz" else "gz"))
        print(f"rebuilt {r['path']}", flush=True)
    return errors


def upload(dry_run: bool, require: bool, rebuild: bool = False) -> int:
    target = s3_target()
    rows = read_index()
    if target is None:
        msg = "IC_ARCHIVE_S3_URI is not set; skipping the S3 upload"
        print(msg, file=sys.stderr)
        return 1 if require else 0
    bucket, prefix = target
    base = f"{prefix}/factor-bases" if prefix else "factor-bases"
    if rebuild:
        errors = rebuild_missing(rows)
        for err in errors:
            print(err, file=sys.stderr)
        if errors:
            return 1
    plan = []
    for row in rows:
        path = HERE / row["path"]
        if not path.exists():
            continue
        for item in archive_paths(path):
            physical = row if row["storage"] != "git-chunks" else {
                **row, "file_sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
            plan.append((item, f"{base}/{row['curve_id']}/{item.name}", physical))
    plan.append((INDEX, f"{base}/index.csv", None))
    # the alias and debt lists and the sweep recipes and shard digests travel with the archive
    extra = [HERE / "aliases.csv", HERE / "unarchived.csv", HERE / "sweeps.csv"]
    extra += sorted((HERE / "sweeps").glob("*.json.gz")) + sorted((HERE / "sweeps").glob("*.points.csv"))
    plan += [(p, f"{base}/{p.relative_to(HERE)}", None) for p in extra if p.exists()]
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
    e.add_argument("--extra", action="append", default=[], metavar="KEY=INT",
                   help="extra integer recipe parameter of an external.py family (a2, stride)")
    e.add_argument("--no-points", action="store_true", help="record the recipe and basis only (B stays null)")
    e.add_argument("--codec", default="gz", choices=["gz", "xz"])
    e.add_argument("--strict-limit", type=int, default=10_000, help="n = 131: count [r]P = O only up to this many points")
    e.add_argument("--max-git-bytes", type=int, default=MAX_GIT_BYTES)
    e.add_argument("--chunk-bytes", type=int, default=0,
                   help="opt in to bounded Git parts for oversized archives; zero keeps S3 behavior")
    s = sub.add_parser("export-suite", help="archive every factor base of an ic-bench suite")
    s.add_argument("--suite", default="full")
    v = sub.add_parser("verify", help="check every archive against the index")
    v.add_argument("--rebuild", action="store_true", help="also rebuild each base from its recipe")
    v.add_argument("--rebuild-max-points", type=int, default=20_000)
    u = sub.add_parser("upload", help="upload the archives and index to $IC_ARCHIVE_S3_URI")
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--require", action="store_true", help="fail instead of skipping when S3 is unavailable")
    u.add_argument("--rebuild-missing", action="store_true",
                   help="first rebuild storage=s3 archives absent here from their recipes (checked by content digest)")
    args = ap.parse_args()
    if args.cmd == "export":
        extra = {k: int(v) for k, v in (kv.split("=", 1) for kv in args.extra)}
        doc = build(args.n, args.family, args.l, args.seed, not args.no_points, args.strict_limit, extra)
        row = store(doc, args.codec, args.max_git_bytes, args.chunk_bytes)
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
        errors += verify_aliases(rows)
        on_disk = {str(p.relative_to(HERE)) for p in (HERE / "bases").rglob("*.json.*")}
        indexed = {r["path"] for r in rows}
        for row in rows:
            path = HERE / row["path"]
            if path.exists() and path.name.endswith(chunked_archive.SUFFIX):
                try:
                    indexed.update(str(p.relative_to(HERE)) for p in archive_paths(path))
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(f"{row['path']}: invalid archive parts: {error}")
        errors += [f"{p}: not in index.csv" for p in sorted(on_disk - indexed)]
        for err in errors:
            print(err)
        print(f"{len(rows)} archives, {len(errors)} problems")
        sys.exit(1 if errors else 0)
    elif args.cmd == "upload":
        sys.exit(upload(args.dry_run, args.require, args.rebuild_missing))


if __name__ == "__main__":
    main()
