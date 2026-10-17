#!/usr/bin/env python3
"""Three five-digit checkpoint rows for the frozen fifteen-digit sparse radix."""

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE / 'native_checkpointed_sparse_overlay.py'
BASE_SHA256 = '66ebf2603ccf8154997d9ef4115b367e0d5ad4315841e432431a138d9634e598'


def main(root: Path):
    assert sha256(BASE.read_bytes()).hexdigest() == BASE_SHA256
    spec = spec_from_file_location('checkpoint3_base', BASE)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    front = root/'src/bin/eisenstein_fixed.rs'
    windows = root/'src/bin/eisenstein_fixed/unit_orbit_windows.rs'
    assert sha256(front.read_bytes()).hexdigest() == module.FRONT_SHA256
    assert sha256(windows.read_bytes()).hexdigest() == module.WINDOWS_SHA256
    tables = module.TABLES.replace('CHECKPOINT_WIDTH: usize = 3;',
                                   'CHECKPOINT_WIDTH: usize = 5;')
    assert tables != module.TABLES and 'CHECKPOINT_WIDTH: usize = 3;' not in tables
    source = windows.read_text()
    start = source.index('struct AltHornerTables {')
    end = source.index('fn alt_horner_mul_pi(',start)
    assert source[start:end].count('static ALT_HORNER_TABLES:') == 1
    source = source[:start]+tables+source[end:]
    start = source.index('    let (seed,unit) = choices[ALT_SPLIT_PRIME_STEPS];',
                         source.index('fn alt_horner_scalar_hex('))
    end = source.index('pub(super) fn multiply_u256_tau_alt_split_prime_two_x_affine_batch(',start)
    source = source[:start]+module.EVALUATE+source[end:]
    windows.write_text(source)
    print('front_sha256='+sha256(front.read_bytes()).hexdigest())
    print('windows_sha256='+sha256(windows.read_bytes()).hexdigest())


if __name__ == '__main__':
    assert len(sys.argv)==2
    main(Path(sys.argv[1]))
