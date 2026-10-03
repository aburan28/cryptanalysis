"""Source-level copy accounting; existing verification counters stay comparable."""


def locality_accounting(certificate, y, equations, mode, *, audit=False):
    stats, old = certificate['partial_locality_stats'], certificate['partial_stats']
    features, limbs = 1 + y + y*(y-1)//2, (equations+63)//64
    assert stats['mode'] == int(mode == 'local')
    assert stats['records'] == old['records']
    assert 0 <= stats['copied_records'] <= stats['records']
    if mode == 'local':
        assert stats['table_loads'] == stats['copy_words'] == stats['copied_records']*features*limbs
        assert stats['cached_loads'] == old['witness_parities']
        assert stats['cache_stack_bytes'] == (112*(4 if equations <= 32 else 8) if stats['copied_records'] else 0)
    else:
        assert stats['table_loads'] == old['witness_parities']
        assert stats['copied_records'] == stats['cached_loads'] == stats['copy_words'] == stats['cache_stack_bytes'] == 0
    assert stats['audit_words'] == (stats['cached_loads'] if audit else 0)


def compare_certificates(actual, expected):
    for field in ('verified', 'code', 'root_count', 'standard_monomials',
                  'coefficient_word_bits', 'solutions', 'ideal_equality', 'reduced_groebner_basis'):
        assert actual.get(field) == expected.get(field), field
    for field in ('stats', 'partial_stats', 'symmetry_check_stats', 'transform_check_stats', 'identity_check_stats'):
        a = {k: v for k, v in actual[field].items() if type(v) in (int, bool)}
        b = {k: v for k, v in expected[field].items() if type(v) in (int, bool)}
        assert a == b, (field, a, b)
