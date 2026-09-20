#!/usr/bin/env python3
"""Overlay the ONE-BLOCK-GEOMETRY 20 B/s knobs onto crypto's modal_app.py.

aburan28/crypto main (#507) builds the 20 B/s binary locally via
`make gpu-rtx-pro6000-20b`, but modal_app.py still:
  - rejects THREADS=512 when ECC_PACKED_STATE_TILE=256
  - does not pass TABLE_TAG_DENOM / TABLE_PIPE_SELECT / PACKED_CHAIN_FIRST /
    PACKED_INLINE_POLY / PACKED_PAIR_ILP / PACKED_L2_PERSIST / PACKED_ALU_SQUARE /
    PACKED_FROM_REDUCED / UNROLL_SLOTS into the image bake or rebuild

This script patches a local checkout in place so Modal can build the same
geometry. Idempotent. Cannot push to aburan28/crypto from this agent.
"""
from __future__ import annotations

import pathlib
import sys

MARKER = "# === ecc2k130-20b overlay (cryptanalysis) ==="

EXTRA_ENV_BLOCK = f"""
{MARKER}
# ONE-BLOCK-GEOMETRY.md / make gpu-rtx-pro6000-20b extras (not on stock modal_app).
TABLE_TAG_DENOM = os.environ.get("ECC_TABLE_TAG_DENOM", "0")
if TABLE_TAG_DENOM not in ("0", "1"):
    raise ValueError("ECC_TABLE_TAG_DENOM must be 0 or 1")
if TABLE_TAG_DENOM == "1" and WALK_TABLE != "1":
    raise ValueError("ECC_TABLE_TAG_DENOM=1 requires ECC_WALK_TABLE=1")
TABLE_PIPE_SELECT = os.environ.get("ECC_TABLE_PIPE_SELECT", "0")
if TABLE_PIPE_SELECT not in ("0", "1"):
    raise ValueError("ECC_TABLE_PIPE_SELECT must be 0 or 1")
PACKED_CHAIN_FIRST = os.environ.get("ECC_PACKED_CHAIN_FIRST", "0")
if PACKED_CHAIN_FIRST not in ("0", "1"):
    raise ValueError("ECC_PACKED_CHAIN_FIRST must be 0 or 1")
PACKED_INLINE_POLY = os.environ.get("ECC_PACKED_INLINE_POLY", "0")
if PACKED_INLINE_POLY not in ("0", "1", "2", "3"):
    raise ValueError("ECC_PACKED_INLINE_POLY must be 0..3")
PACKED_PAIR_ILP = os.environ.get("ECC_PACKED_PAIR_ILP", "0")
if PACKED_PAIR_ILP not in ("0", "1"):
    raise ValueError("ECC_PACKED_PAIR_ILP must be 0 or 1")
PACKED_L2_PERSIST = os.environ.get("ECC_PACKED_L2_PERSIST", "0")
if PACKED_L2_PERSIST not in ("0", "1"):
    raise ValueError("ECC_PACKED_L2_PERSIST must be 0 or 1")
PACKED_ALU_SQUARE = os.environ.get("ECC_PACKED_ALU_SQUARE", "0")
if PACKED_ALU_SQUARE not in ("0", "1"):
    raise ValueError("ECC_PACKED_ALU_SQUARE must be 0 or 1")
PACKED_FROM_REDUCED = os.environ.get("ECC_PACKED_FROM_REDUCED", "0")
if PACKED_FROM_REDUCED not in ("0", "1"):
    raise ValueError("ECC_PACKED_FROM_REDUCED must be 0 or 1")
UNROLL_SLOTS = os.environ.get("ECC_UNROLL_SLOTS", "1")
if not UNROLL_SLOTS.isdigit() or not (1 <= int(UNROLL_SLOTS) <= 16):
    raise ValueError("ECC_UNROLL_SLOTS must be 1..16")
"""


def patch(path: pathlib.Path) -> None:
    text = path.read_text()
    if MARKER in text:
        print(f"already patched: {path}")
        return

    # Allow 512-thread one-block geometry with TILE256 (measured 20 B/s).
    old_check = (
        '    if PACKED_STATE_TILE == "256" and threads != 256:\n'
        '        return False, "ECC_PACKED_STATE_TILE=256 requires 256 threads per block"'
    )
    new_check = (
        '    if PACKED_STATE_TILE == "256" and threads not in (256, 512):\n'
        '        return False, "ECC_PACKED_STATE_TILE=256 requires 256 or 512 threads per block"'
    )
    if old_check not in text:
        raise SystemExit("expected TILE256 threads check not found; modal_app.py changed")
    text = text.replace(old_check, new_check, 1)

    anchor = 'PACKED_STATE_TILE = os.environ.get("ECC_PACKED_STATE_TILE", "0")'
    if anchor not in text:
        raise SystemExit("PACKED_STATE_TILE anchor missing")
    text = text.replace(anchor, EXTRA_ENV_BLOCK + "\n" + anchor, 1)

    env_anchor = '"ECC_TABLE_PIVOT_BYTES": TABLE_PIVOT_BYTES,'
    env_extra = (
        '"ECC_TABLE_PIVOT_BYTES": TABLE_PIVOT_BYTES,\n'
        '          "ECC_TABLE_TAG_DENOM": TABLE_TAG_DENOM,\n'
        '          "ECC_TABLE_PIPE_SELECT": TABLE_PIPE_SELECT,\n'
        '          "ECC_PACKED_CHAIN_FIRST": PACKED_CHAIN_FIRST,\n'
        '          "ECC_PACKED_INLINE_POLY": PACKED_INLINE_POLY,\n'
        '          "ECC_PACKED_PAIR_ILP": PACKED_PAIR_ILP,\n'
        '          "ECC_PACKED_L2_PERSIST": PACKED_L2_PERSIST,\n'
        '          "ECC_PACKED_ALU_SQUARE": PACKED_ALU_SQUARE,\n'
        '          "ECC_PACKED_FROM_REDUCED": PACKED_FROM_REDUCED,\n'
        '          "ECC_UNROLL_SLOTS": UNROLL_SLOTS,'
    )
    if env_anchor not in text:
        raise SystemExit("image .env TABLE_PIVOT_BYTES anchor missing")
    text = text.replace(env_anchor, env_extra, 1)

    # Image bake uses f'...'; buildFor uses f"...".
    extras = (
        " TABLE_TAG_DENOM={TABLE_TAG_DENOM} TABLE_PIPE_SELECT={TABLE_PIPE_SELECT}"
        " PACKED_CHAIN_FIRST={PACKED_CHAIN_FIRST} PACKED_INLINE_POLY={PACKED_INLINE_POLY}"
        " PACKED_PAIR_ILP={PACKED_PAIR_ILP} PACKED_L2_PERSIST={PACKED_L2_PERSIST}"
        " PACKED_ALU_SQUARE={PACKED_ALU_SQUARE} PACKED_FROM_REDUCED={PACKED_FROM_REDUCED}"
        " UNROLL_SLOTS={UNROLL_SLOTS}"
    )
    replaced = 0
    for quote in ("'", '"'):
        old_tail = f"WALK_TABLE={{WALK_TABLE}} TABLE_PIVOT_BYTES={{TABLE_PIVOT_BYTES}}{quote}"
        new_tail = (
            "WALK_TABLE={WALK_TABLE} TABLE_PIVOT_BYTES={TABLE_PIVOT_BYTES}"
            + extras
            + quote
        )
        n = text.count(old_tail)
        if n:
            text = text.replace(old_tail, new_tail)
            replaced += n
    if replaced < 2:
        raise SystemExit(f"expected >=2 make tails, found {replaced}")

    baked_threads = (
        'BAKED = {"batch": 32, "threads": 256 if PACKED_STATE_TILE == "256" else 128, '
        '"leaf": 0, "minBlocks": 2,'
    )
    baked_threads_new = (
        'BAKED = {"batch": 16 if TABLE_TAG_DENOM == "1" else 32, '
        '"threads": (512 if TABLE_TAG_DENOM == "1" else (256 if PACKED_STATE_TILE == "256" else 128)), '
        '"leaf": 0, "minBlocks": 1 if TABLE_TAG_DENOM == "1" else 2,'
    )
    if baked_threads not in text:
        raise SystemExit("BAKED default shape not found")
    text = text.replace(baked_threads, baked_threads_new, 1)

    # runSearch calls buildFor without minBlocks (defaults to 2). Force the
    # one-block shape when the 20 B/s overlay env is active.
    old_search_build = "        ok, log = buildFor(batch, threads, leaf)"
    new_search_build = (
        "        ok, log = buildFor(batch, threads, leaf, "
        'minBlocks=1 if TABLE_TAG_DENOM == "1" else 2)'
    )
    if old_search_build not in text:
        raise SystemExit("runSearch buildFor call not found")
    text = text.replace(old_search_build, new_search_build, 1)

    path.write_text(text)
    print(f"patched: {path}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} /path/to/ecc2k130/modal_app.py")
    path = pathlib.Path(sys.argv[1])
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    patch(path)


if __name__ == "__main__":
    main()
