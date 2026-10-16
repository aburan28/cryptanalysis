#!/usr/bin/env python3
"""Check every native norm-4033 selector output against an independent lattice search."""

from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import tarfile

HERE = Path(__file__).resolve().parent
NORM = 4033
WINDOWS = 'bench-sources/prime-j0-sparse-radix4033/src/bin/eisenstein_fixed/unit_orbit_windows.rs'


def digest(data):
    return sha256(data).hexdigest()


def norm(a, b):
    return a*a + 3*a*b + 3*b*b


def native_selector_model(residue):
    if residue == 0:
        return 0, 0
    candidates = []
    for lift_number in range(-2, 3):
        lift = residue + lift_number*NORM
        center = (127*lift)//8066
        for b in range(center-2, center+3):
            a = lift-65*b
            candidates.append((norm(a,b), abs(b), abs(a), a, b))
    _, _, _, a, b = min(candidates)
    return a, b


def independent_minimum(residue):
    # If norm < 4033, 4*norm=(2a+3b)^2+3b^2 implies |b|<74.
    # For these b and 0<=residue<=2016, |k|>=3 makes |a|>4000 in
    # a=residue-65b+4033k, hence norm >= a^2/4 > 4033.
    return min(
        (norm(a,b), abs(b), abs(a), a, b)
        for b in range(-73,74)
        for k in range(-2,3)
        for a in [residue-65*b+NORM*k]
    )


def main():
    overlay_path = HERE/'native_sparse_radix4033_overlay.py'
    spec = importlib.util.spec_from_file_location('radix4033_overlay', overlay_path)
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    provenance_path = HERE/'radix4033-native-provenance.tar.gz'
    rules = json.loads((HERE/'tier1-radix4033-128-cpu40-rules.json').read_text())
    with tarfile.open(provenance_path, 'r:gz') as archive:
        windows = archive.extractfile(WINDOWS).read()
        front = archive.extractfile(
            'bench-sources/prime-j0-sparse-radix4033/src/bin/eisenstein_fixed.rs').read()
    assert digest(windows) == rules['hashes']['candidate_windows']
    assert digest(front) == rules['hashes']['candidate_front']
    assert digest(overlay_path.read_bytes()) == rules['hashes']['candidate_overlay']
    assert overlay.NEW_SELECTOR in windows.decode()
    assert overlay.NEW_STEP in windows.decode()
    assert overlay.NEW_HORNER in windows.decode()
    assert 'let negative = residue > ALT_SPLIT_PRIME_DIGIT_LIMIT;' in windows.decode()
    assert 'let index = if negative { ALT_SPLIT_PRIME_NORM as usize-residue as usize }' in windows.decode()
    assert 'let da = if negative { -i32::from(raw_da) }' in windows.decode()
    assert 'let db = if negative { -i32::from(raw_db) }' in windows.decode()
    max_norm = max_abs_a = max_abs_b = 0
    for residue in range(2017):
        a,b = native_selector_model(residue)
        score = (norm(a,b),abs(b),abs(a),a,b)
        assert score == independent_minimum(residue), residue
        assert (a+65*b-residue) % NORM == 0
        assert norm(a,b) < NORM
        rounded_b = (127*residue+NORM)//(2*NORM)
        assert norm(a,b) <= norm(residue-65*rounded_b,rounded_b)
        if residue:
            signed_residue = NORM-residue
            assert (-a+65*(-b)-signed_residue) % NORM == 0
            assert norm(-a,-b) == norm(a,b)
        max_norm = max(max_norm,norm(a,b))
        max_abs_a = max(max_abs_a,abs(a))
        max_abs_b = max(max_abs_b,abs(b))
    receipt = {
        'schema':1,
        'residue_classes_checked':2017,
        'independent_minimum_matches':2017,
        'signed_residue_classes_covered_by_negation':4033,
        'max_digit_norm':max_norm,
        'max_abs_a':max_abs_a,
        'max_abs_b':max_abs_b,
        'all_digits_below_radix_norm':True,
        'candidate_windows_sha256':digest(windows),
        'candidate_front_sha256':digest(front),
        'overlay_sha256':digest(overlay_path.read_bytes()),
        'provenance_sha256':digest(provenance_path.read_bytes()),
    }
    (HERE/'radix4033-selector-audit.json').write_text(
        json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
