"""Reconstruct identity-stage inputs from original ANF and retained full proofs."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import numpy as np

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / 'round40/fixtures/inputs.json.gz'
TAG = 1 << 63


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(destination):
    manifest = json.loads((HERE / 'fixtures/manifest.json').read_text())
    assert manifest['fixture_sha256'] == sha(FIXTURE)
    items = {v['name']: v for v in json.loads(gzip.decompress(FIXTURE.read_bytes()))}
    destination.mkdir(exist_ok=False, parents=True)
    records = []
    for saved in manifest['records']:
        item = items[saved['name']]
        assert item['workload_sha256'] == saved['workload_sha256']
        x, y, equations = 2 * item['ell'], item['ell'], item['n']
        limbs, branches = (equations + 63) // 64, 1 << x
        features = [m for m in range(1 << y) if m.bit_count() <= 2]
        index = {m: i for i, m in enumerate(features)}
        dtype = '<u4' if equations <= 32 else '<u8'
        table = np.zeros((len(features) * limbs, branches), dtype=dtype)
        for mask, coefficient in item['reference_anf']:
            assert mask >> (x + y) == 0 and (mask >> x) in index
            assert 0 <= coefficient < (1 << equations)
            for limb in range(limbs):
                word = (coefficient >> (64 * limb)) & ((1 << 64) - 1)
                table[index[mask >> x] * limbs + limb, mask & (branches - 1)] ^= np.array(word, dtype=dtype)
        # Exact symmetry of the original scattered coefficients, before transformation.
        branch_ids = np.arange(branches, dtype=np.uint32)
        swapped = ((branch_ids & ((1 << y) - 1)) << y) | (branch_ids >> y)
        assert np.array_equal(table, table[:, swapped])
        # Feature-major, descending-bit Boolean subset transform, independently
        # reconstructed from original polynomials without producer native code.
        for bit in range(x - 1, -1, -1):
            shaped = table.reshape(table.shape[0], -1, 2, 1 << bit)
            shaped[:, :, 1, :] ^= shaped[:, :, 0, :]
        proof_path = HERE / 'fixtures' / saved['proof_file']
        assert sha(proof_path) == saved['proof_file_sha256']
        raw = gzip.decompress(proof_path.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == saved['proof_sha256']
        proof = np.frombuffer(raw, dtype='<u8')
        prefix, entry = branches * limbs, 1 + (y + 1) * limbs
        assert len(proof) >= prefix and (len(proof) - prefix) % entry == 0
        extension = proof[prefix:].reshape(-1, entry)
        metadata = {}
        previous = -1
        for row in extension:
            tagged = int(row[0]); branch = tagged & ~TAG
            assert previous < branch < branches
            previous = branch
            assert not any(proof[branch * limbs:(branch + 1) * limbs])
            metadata[branch] = (bool(tagged & TAG), row[1:])
        # Reproduce only the validated identical-proof symmetry aliases. A
        # differing or absent witness remains a full independent check.
        selected, witnesses, skipped = [], [], 0
        for branch, (partial, words) in metadata.items():
            if partial:
                continue
            partner = int(swapped[branch])
            other = metadata.get(partner)
            alias = branch > partner and other is not None and not other[0] and np.array_equal(words, other[1])
            if alias:
                skipped += 1
                continue
            if equations % 64:
                assert not any(int(v) >> (equations % 64) for v in words[limbs - 1::limbs])
            selected.append(branch)
            witnesses.extend(map(int, words))
        assert len(selected) == saved['attempted_records'] and skipped == saved['reused_records']
        path = destination / (saved['name'] + '.bin')
        with path.open('xb') as output:
            output.write(b'MUL69V1\0' + struct.pack('<4I', x, y, equations, len(selected)))
            output.write(table.tobytes(order='C'))
            output.write(np.asarray(selected, dtype='<u4').tobytes())
            output.write(np.asarray(witnesses, dtype='<u8').tobytes())
        records.append(dict(saved, input_path=str(path.resolve()), input_sha256=sha(path),
                            x=x, y=y, equations=equations, coefficient_bytes=table.nbytes,
                            records=len(selected), skipped_aliases=skipped))
    return records
