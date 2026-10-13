#!/usr/bin/env python3
"""Account for a single-tree, pre-tau mixed-radix scalar evaluator."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-mixed-radix640-20261010"
sys.path.insert(0, str(HERE.parent / "prime-j0-tau-power16-20261010"))
import verify_group as reference  # noqa: E402; must precede the mixed module

spec = importlib.util.spec_from_file_location("mixed640_group", PARENT / "verify_group.py")
mixed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mixed)


def atlas_records():
    result = {}
    for label, path, radix, magic in (
        ("512", mixed.ATLAS512, 512, b"T2B9"),
        ("640", mixed.ATLAS640, 640, b"T640"),
        ("391", mixed.ATLAS391, 640, b"T640"),
    ):
        atlas = mixed.Atlas(path, radix, magic)
        tau_ids = {code >> 4 for (code,) in struct.iter_unpack("<I", atlas.codes)
                   if (code >> 3) & 1}
        assert 0 not in tau_ids
        result[label] = (atlas, {"seed_count": atlas.count,
                                 "tau_seed_count": len(tau_ids),
                                 "sha256": sha256(path.read_bytes()).hexdigest()})
    return result


def tree_calls(n):
    return 0 if n < 2 else 10 * n - 14


def main():
    atlases = atlas_records()
    source = PARENT / "fresh-inputs.json"
    scalars = json.loads(source.read_bytes())["scalars_hex"]
    histogram = Counter()
    replay_count = 64
    output_hash = sha256()
    for case, scalar_hex in enumerate(scalars):
        scalar = int(scalar_hex, 16) % mixed.screen.ORDER
        a, b = mixed.screen.representative(scalar)
        choices = []
        for index, radix in enumerate(mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            atlas = atlases[label][0]
            digit, seed_id, exponent, unit = atlas.decode(a, b)
            if seed_id:
                choices.append((index, seed_id, exponent, unit))
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
        counts = (sum(e == 0 for _, _, e, _ in choices),
                  sum(e == 1 for _, _, e, _ in choices))
        histogram[counts] += 1
        if case < replay_count:
            # Build window bases independently of the scalar oracle.
            bases = [reference.G]
            for radix in mixed.RADICES[:-1]:
                bases.append(reference.multiply(radix, bases[-1]))
            unified = None
            for index, seed_id, exponent, unit in choices:
                label = "512" if index < 6 else "391" if index == 13 else "640"
                sa, sb = atlases[label][0].seed(seed_id)
                seed = reference.add(reference.multiply(sa, bases[index]),
                                     reference.multiply(sb, reference.tau_point(bases[index])))
                entry = reference.tau_point(seed) if exponent else seed
                unified = reference.add(unified, reference.unit_point(entry, unit))
            expected = reference.multiply(scalar, reference.G)
            assert unified == expected, case
            output_hash.update(bytes(64) if unified is None else
                               unified[0].to_bytes(32, "big") + unified[1].to_bytes(32, "big"))

    slots = 6 * atlases["512"][1]["seed_count"] + 7 * atlases["640"][1]["seed_count"] + atlases["391"][1]["seed_count"]
    tau_slots = 6 * atlases["512"][1]["tau_seed_count"] + 7 * atlases["640"][1]["tau_seed_count"] + atlases["391"][1]["tau_seed_count"]
    assert slots == 415190
    two_bucket_calls = sum((tree_calls(n0) + tree_calls(n1) +
                            (14 if n0 and n1 else 0) + (9 if n1 else 0)) * count
                           for (n0, n1), count in histogram.items())
    unified_calls = sum(tree_calls(n0 + n1) * count
                        for (n0, n1), count in histogram.items())
    atlas_bytes = sum(path.stat().st_size for path in
                      (mixed.ATLAS512, mixed.ATLAS640, mixed.ATLAS391))
    # The 512 atlas is shared by six windows; the 640 full atlas by seven.
    record = {"schema": 1, "status": "operation_model_and_affine_replay",
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "input_sha256": sha256(source.read_bytes()).hexdigest(),
              "cases": len(scalars), "affine_replay_cases": replay_count,
              "affine_replay_output_sha256": output_hash.hexdigest(),
              "atlas": {key: val[1] for key, val in atlases.items()},
              "bucket_histogram": {f"{n0},{n1}": count for (n0, n1), count in sorted(histogram.items())},
              "point_slots": slots, "tau_image_slots": tau_slots,
              "two_bucket_join_and_tau_calls": two_bucket_calls,
              "unified_tree_join_calls": unified_calls,
              "saved_calls": two_bucket_calls - unified_calls,
              "two_bucket_96byte_point_and_atlas_bytes": slots * 96 + atlas_bytes,
              "unified_96byte_point_and_atlas_bytes": (slots + tau_slots) * 96 + atlas_bytes,
              "excluded": ["table_construction", "recoding", "memory_traffic",
                           "affine_recovery", "host_wall_time"]}
    output = HERE / "model.json"
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    else:
        assert len(sys.argv) == 1
        assert json.loads(output.read_bytes()) == record
    print(json.dumps({k: record[k] for k in ("cases", "affine_replay_cases",
                                          "point_slots", "tau_image_slots",
                                          "two_bucket_join_and_tau_calls",
                                          "unified_tree_join_calls", "saved_calls")}, sort_keys=True))


if __name__ == "__main__":
    main()
