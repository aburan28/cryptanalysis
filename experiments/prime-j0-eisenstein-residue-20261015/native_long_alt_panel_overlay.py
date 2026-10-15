#!/usr/bin/env python3
"""Build a longer matched timing interval from the frozen two-x Rust sources."""

from hashlib import sha256
from pathlib import Path
import sys

CACHE10_FRONT_SHA256 = '99b6323f52f2f6eb7e4a8a2c4056ad7b9ebce29571a9ec4187fd4212097a3756'
ALT_FRONT_SHA256 = '2f4f14749e4c655a7dfd56d09eae077f2142c802377ab0f5f0f52b35d7272be0'
OUTER_REPEATS = 10


def replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new)


def transform(path: Path, expected_sha256: str, function_name: str) -> dict:
    original = path.read_bytes()
    assert sha256(original).hexdigest() == expected_sha256
    source = original.decode()
    start = source.index(f'fn {function_name}(')
    end = source.find('\nfn ', start+1)
    assert end > start
    body = source[start:end]
    body = replace_once(body,
        'let mut answers = Vec::with_capacity(inputs.len());',
        f'let mut answers = Vec::with_capacity(inputs.len()*{OUTER_REPEATS});')
    body = replace_once(body,
        '    for chunk in words.chunks(batch_size) {',
        f'    for _ in 0..{OUTER_REPEATS} {{\n        for chunk in words.chunks(batch_size) {{')
    body = replace_once(body,
        '    let online_ms = start.elapsed().as_secs_f64()*1000.0;',
        '    }\n    let online_ms = start.elapsed().as_secs_f64()*1000.0;')
    body = replace_once(body,
        'assert_eq!(answers.len(),inputs.len());',
        f'assert_eq!(answers.len(),inputs.len()*{OUTER_REPEATS});')
    body = replace_once(body,
        'assert_eq!(point,inputs[index].1,"stream case {index}");',
        'assert_eq!(point,inputs[index%inputs.len()].1,"stream case {index}");')
    body = replace_once(body,
        'batch_id=uniform128x96',
        f'batch_id=uniform128x96x{OUTER_REPEATS}')
    updated = (source[:start]+body+source[end:]).encode()
    path.write_bytes(updated)
    return {'path':str(path), 'input_sha256':sha256(original).hexdigest(),
            'output_sha256':sha256(updated).hexdigest(),
            'function':function_name,'outer_repeats':OUTER_REPEATS}


def main(cache10_root: Path, alt_root: Path) -> None:
    front = Path('src/bin/eisenstein_fixed.rs')
    for result in (
        transform(cache10_root/front, CACHE10_FRONT_SHA256,
                  'benchmark_mixed640_cache_budget_uniform'),
        transform(alt_root/front, ALT_FRONT_SHA256,
                  'benchmark_mixed640_alt_radix_uniform'),
    ):
        print(result)


if __name__ == '__main__':
    assert len(sys.argv) == 3
    main(Path(sys.argv[1]), Path(sys.argv[2]))
