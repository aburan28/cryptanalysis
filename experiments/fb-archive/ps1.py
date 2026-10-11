"""Link experiment cells to archived factor bases and give each a PS1 label.

AGENTS.md: a measured PDP-stage profile of an exact base without final relation LA
or target descent is labelled PS1N<n>C<curve-tag>fb<B>PDP<m><solver>h<12hex>, the
digest hashing its factor-base and point-decomposition records.  Here the
factor-base record is identified by its archived `factor_base_sha256` and the
point-decomposition record is supplied by the experiment.

    from ps1 import cell_manifest
    cell_manifest(n=11, family="nbweight", l=2, pdp=PDP_RECORD)
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

from toycurve import sha256_hex  # noqa: E402  (fbarchive puts pdp-degree-heuristics on sys.path)


def source_sha256(paths: list[str]) -> dict:
    """Content digests of the executed sources, by repository-relative path."""
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def index_row(n: int, family: str, l: int, seed: int = 1) -> dict:
    with open(HERE / "index.csv", newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if (int(r["n"]), r["family"], int(r["l"]), int(r["seed"])) == (n, family, l, seed)]
    if len(rows) != 1:
        raise LookupError(f"expected one archive row for n={n} {family} l={l} s={seed}, found {len(rows)}")
    return rows[0]


def cell_manifest(n: int, family: str, l: int, pdp: dict, seed: int = 1) -> dict:
    row = index_row(n, family, l, seed)
    m = re.fullmatch(r"EC1N(\d+)C([a-z0-9]+)h[0-9a-f]{12}", row["curve_id"])
    if m is None or int(m.group(1)) != n:
        raise ValueError(f"unexpected curve ID {row['curve_id']}")
    tag = m.group(2)
    digest = sha256_hex({"factor_base_sha256": row["factor_base_sha256"], "point_decomposition": pdp})
    label = f"PS1N{n}C{tag}fb{row['fb_points']}PDP{pdp['m']}{pdp['solver']}h{digest[:12]}"
    return {
        "n": n, "family": family, "l": l, "seed": seed,
        "curve_id": row["curve_id"],
        "factor_base_sha256": row["factor_base_sha256"],
        "enumerated_set_sha256": row["enumerated_set_sha256"],
        "fb_points": int(row["fb_points"]),
        "effective_columns": int(row["effective_columns"]),
        "archive_path": "experiments/fb-archive/" + row["path"],
        "ps1_label": label,
        "candidate_id": None,
    }
