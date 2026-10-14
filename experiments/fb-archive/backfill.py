#!/usr/bin/env python3
"""Archive factor bases that committed results cite but index.csv lacks.

For every cited digest (see refs.py: `factor_base_sha256` or a point-set digest
such as `enumerated_set_sha256`) in the named experiments that is not yet
archived, find the recipe recorded beside it -- a `cell` object with
n, family, l and seed, on the citing row or an ancestor -- rebuild the base with
fbarchive.build, and store it only if the rebuilt `factor_base_sha256` equals the
cited one -- the record digest for a record citation, the enumerated-set digest
for a point-set citation. A digest whose recipe is missing, or whose rebuild differs, is
reported and left alone: it stays debt in unarchived.csv.

    python3 backfill.py experiments/fb-search experiments/pdp-degree-heuristics [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import fbarchive
import refs

RECIPE_KEYS = ("n", "family", "l", "seed")


def recipe_of(cell) -> tuple | None:
    if isinstance(cell, dict) and all(k in cell for k in RECIPE_KEYS):
        try:
            return (int(cell["n"]), str(cell["family"]), int(cell["l"]), int(cell["seed"]))
        except (TypeError, ValueError):
            return None
    return None


def collect(obj, inherited: tuple | None, out: dict[str, set[tuple]]) -> None:
    if isinstance(obj, dict):
        here = recipe_of(obj.get("cell")) or recipe_of(obj.get("recipe")) or inherited
        for key in refs.KEYS:
            d = obj.get(key)
            if isinstance(d, str) and refs.HEX64.fullmatch(d) and here is not None:
                out.setdefault(d, set()).add(here)
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                collect(v, here, out)
    elif isinstance(obj, list):
        for v in obj:
            collect(v, inherited, out)


def recipes_in(rel: str) -> dict[str, set[tuple]]:
    text = refs.read_text(refs.ROOT / rel)
    out: dict[str, set[tuple]] = {}
    if not any(k in text for k in refs.KEYS):
        return out
    try:
        collect(json.loads(text), None, out)
        return out
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                collect(json.loads(line), None, out)
            except json.JSONDecodeError:
                pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiments", nargs="+", help="experiment directories, repository-relative")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    prefixes = tuple(e.rstrip("/") + "/" for e in args.experiments)
    have = refs.archived()
    wanted: dict[str, set[tuple]] = {}
    for rel in refs.tracked_files():
        if rel.startswith(prefixes):
            for d, rs in recipes_in(rel).items():
                if d not in have:
                    wanted.setdefault(d, set()).update(rs)
    cited = {d for d, files in refs.citations().items()
             if d not in have and any(f.startswith(prefixes) for f in files)}
    no_recipe = sorted(cited - set(wanted))
    print(f"{len(cited)} unarchived digests cited, {len(wanted)} with a recorded recipe, "
          f"{len(no_recipe)} without", flush=True)
    stored = mismatched = 0
    t0 = time.time()
    # build each recipe once even when several digests point at it
    by_recipe: dict[tuple, set[str]] = {}
    for d, rs in wanted.items():
        for r in rs:
            by_recipe.setdefault(r, set()).add(d)
    done: set[str] = set()
    for i, (r, ds) in enumerate(sorted(by_recipe.items())):
        if ds <= done:
            continue
        n, family, l, seed = r
        try:
            doc = fbarchive.build(n, family, l, seed)
        except Exception as exc:  # noqa: BLE001 -- report and keep going
            print(f"  build failed {r}: {exc}", flush=True)
            continue
        got = {doc["factor_base_sha256"], doc["factor_base"]["enumerated_set_sha256"]}
        if got & ds:
            if not args.dry_run:
                fbarchive.store(doc)
            done |= got
            stored += 1
        else:
            mismatched += 1
            print(f"  rebuild of {r} gives {sorted(x[:12] for x in got)}, cited {sorted(x[:12] for x in ds)}",
                  flush=True)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(by_recipe)} recipes, {stored} stored, {time.time() - t0:.0f}s", flush=True)
    left = sorted(cited - done)
    print(f"stored {stored}, rebuild mismatches {mismatched}, still unarchived {len(left)}")
    for d in no_recipe[:20]:
        print(f"  no recipe recorded: {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
