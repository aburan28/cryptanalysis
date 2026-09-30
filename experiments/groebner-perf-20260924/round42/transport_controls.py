"""Exact binary-linear transport controls; no timing claims."""
import hashlib
import random
import normalized as candidate


def multiply(a, b, modulus):
    n = modulus.bit_length() - 1
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a >> n:
            a ^= modulus
    return result


def validate_transport_tables():
    """Check every nibble entry against direct polynomial multiplication."""
    ct = candidate.ct
    rng = random.Random(202609304601)
    records = []
    for n in range(6, 32):
        modulus = (1 << n) | 3
        mask = (1 << n) - 1
        values = {0, mask, 1 << (n - 1)}
        values.update((v << (4 * nibble)) & mask for nibble in range((n + 3) // 4) for v in range(16))
        values.update(rng.getrandbits(n) for _ in range(16))
        if n == 7:
            values.update(range(128))
        # Independent polynomial products are reused only inside this test.
        columns = {v: [multiply(v, 1 << e, modulus) for e in range(n)] for v in values}
        for y in range(3, min(10, (n + 3) // 3) + 1):
            top = 3 * y - 4
            annihilator = [1, sum(1 << i for i in range(1, top + 1) if i % 3 == 0),
                           sum(1 << i for i in range(1, top + 1) if i % 3)]
            annihilator += [1 << i for i in range(top + 1, n)]
            expected = {v: [sum(((a & col).bit_count() & 1) << e for e, col in enumerate(cols))
                            for a in annihilator] for v, cols in columns.items()}
            for sanitizer in (False, True):
                with candidate.Producer(1, y, n, sanitizer=sanitizer) as producer:
                    assert producer.configure_normalization(modulus)
                    fn = producer.lib.branch_normalization_transport
                    digest = hashlib.sha256()
                    for value in sorted(values):
                        output = (ct.c_uint32 * 33)(*[0xdeadbeef] * 33)
                        count = fn(producer._handle, value, output, 32)
                        assert count == len(annihilator)
                        assert list(output[:count]) == expected[value], (n, y, value, sanitizer)
                        assert list(output[count:]) == [0xdeadbeef] * (33 - count)
                        digest.update(value.to_bytes(4, 'little'))
                        for word in output[:count]:
                            digest.update(word.to_bytes(4, 'little'))
                    output = (ct.c_uint32 * 33)(*[0xdeadbeef] * 33)
                    assert fn(producer._handle, 0, output, len(annihilator) - 1) == -1
                    assert fn(producer._handle, 1 << n, output, 32) == -1
                    assert fn(producer._handle, 0, None, 32) == -1
                    assert fn(None, 0, output, 32) == -1
                    assert list(output) == [0xdeadbeef] * 33
                    assert not producer.configure_normalization(0)
                    assert fn(producer._handle, 0, output, 32) == -1
                    assert list(output) == [0xdeadbeef] * 33
                    # Reconfiguration builds a different quotient's exact map.
                    alternate = (1 << n) | 9
                    assert producer.configure_normalization(alternate)
                    value = mask
                    count = fn(producer._handle, value, output, 32)
                    alternate_columns = [multiply(value, 1 << e, alternate) for e in range(n)]
                    assert list(output[:count]) == [sum(((a & col).bit_count() & 1) << e
                        for e, col in enumerate(alternate_columns)) for a in annihilator]
                    assert count == len(annihilator)
                    records.append({'equations': n, 'residual_variables': y, 'sanitizer': sanitizer,
                                    'values': len(values), 'output_sha256': digest.hexdigest(),
                                    'extent_guards': 5, 'reconfigured_modulus': alternate})
    print('TRANSPORT_TABLES_PASS', len(records), 'shape/build records;', sum(r['values'] for r in records), 'values', flush=True)
    return records

