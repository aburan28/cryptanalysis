#!/usr/bin/env python3
"""Add two frozen SHAKE-derived scalar batch modes to the final stream binary."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "76417bc6ae1d9eb2f219ffc89b758163cf165cc76793a4fdb654f117f9da1315"
OLD_FIXTURE_SHA256 = "6b7ce3b515d0980b9975398b8b31e5e1cfdc9e54510d04faf29fee3f3bacf778"
FIXTURE_SHA256 = "a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3"


def main(root):
    front = root / "src/bin/eisenstein_fixed.rs"
    fixture = root / "src/bin/mixed640_uniform_fixture.json"
    source = front.read_text()
    assert sha256(source.encode()).hexdigest() == FRONT_SHA256
    assert sha256(fixture.read_bytes()).hexdigest() == FIXTURE_SHA256
    first = source.index("fn benchmark_mixed640_two_x_stream(")
    second = source.index("fn benchmark_mixed640_cache_budget_stream(", first)
    third = source.index("fn benchmark_mixed640_affine_layer_stream(", second)
    end = source.index("\nfn main()", third)
    two_x = source[first:second]
    affine = source[third:end]
    for old, block in (("two_x_stream", two_x),
                       ("affine_layer_stream", affine)):
        assert block.count("mixed640_stream_fixture.json") == 1
        assert block.count(OLD_FIXTURE_SHA256) == 1
    two_x = two_x.replace("two_x_stream", "two_x_uniform")
    affine = affine.replace("affine_layer_stream", "affine_layer_uniform")
    blocks = []
    for block in (two_x, affine):
        blocks.append(block.replace("mixed640_stream_fixture.json",
                                    "mixed640_uniform_fixture.json")
                     .replace(OLD_FIXTURE_SHA256, FIXTURE_SHA256)
                     .replace("stream128x96", "uniform128x96"))
    updated = source[:end] + "\n" + "\n".join(blocks) + source[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-affine-two-x-uniform" {
        benchmark_mixed640_two_x_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
    if args.len() == 3 && args[0] == "--benchmark-split-prime-affine-layer-uniform" {
        benchmark_mixed640_affine_layer_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert updated.count(needle) == 1
    updated = updated.replace(needle, needle + dispatch, 1)
    front.write_text(updated)
    print("front_sha256=" + sha256(updated.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
