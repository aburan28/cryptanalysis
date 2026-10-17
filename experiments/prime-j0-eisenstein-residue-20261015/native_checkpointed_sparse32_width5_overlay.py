#!/usr/bin/env python3
"""Four five-digit checkpoints for the frozen 31+32*tau native path."""

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE / 'native_checkpointed_sparse_overlay.py'
BASE_SHA256 = '66ebf2603ccf8154997d9ef4115b367e0d5ad4315841e432431a138d9634e598'
FRONT_SHA256 = '6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34'
WINDOWS_SHA256 = '3bba985851048b4fa7431e8ace04658e341b0ccda469116e7c9bcbb7b54cba3d'


def once(source: str, before: str, after: str) -> str:
    assert source.count(before) == 1, before
    return source.replace(before, after, 1)


def main(root: Path) -> None:
    assert sha256(BASE.read_bytes()).hexdigest() == BASE_SHA256
    spec = spec_from_file_location('checkpoint_sparse32_base', BASE)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    front = root / 'src/bin/eisenstein_fixed.rs'
    windows = root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == WINDOWS_SHA256

    tables = module.TABLES
    for before, after in (
        ('CHECKPOINT_WIDTH: usize = 3;', 'CHECKPOINT_WIDTH: usize = 5;'),
        ('127+128*tau', '31+32*tau'),
        ('affine_multiples(mixed,128)', 'affine_multiples(mixed,32)'),
        ('digit_pairs.len(),57025', 'digit_pairs.len(),3505'),
        ('digit_seeds.len(),19009', 'digit_seeds.len(),1169'),
        ('pi^15 G', 'pi^20 G'),
    ):
        tables = once(tables, before, after)
    source = windows.read_text()
    start = source.index('struct AltHornerTables {')
    end = source.index('fn alt_horner_mul_pi(', start)
    assert source[start:end].count('static ALT_HORNER_TABLES:') == 1
    source = source[:start] + tables + source[end:]
    start = source.index('    let (seed,unit) = choices[ALT_SPLIT_PRIME_STEPS];',
                         source.index('fn alt_horner_scalar_hex('))
    end = source.index('pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(',
                       start)
    source = source[:start] + module.EVALUATE + source[end:]
    windows.write_text(source)
    print('front_sha256=' + sha256(front.read_bytes()).hexdigest())
    print('windows_sha256=' + sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv) == 2
    main(Path(sys.argv[1]))
