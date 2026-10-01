"""Independent integer accounting for the optional specialization kernels."""

MODES = {'full': 0, 'axes': 1, 'tile8': 2, 'tile16': 3, 'tile32': 4, 'hoisted': 5}
CONTROL_MODES = ('full', 'axes', 'tile16')
QUERY_MODES = tuple(MODES)


def recursive_counts(k):
    if k <= 4:
        return k * (1 << (2*k)), 0
    xors, copies = recursive_counts(k-1)
    h = 1 << (k-1)
    return (2*xors + (k-1)*h*h + 3*h*(h-1)//2 + h + h*h,
            2*copies + h*(h-1)//2 + h*h)


def reconcile_transform(check, x, y, equations, *, audit=None):
    t = check['transform_check_stats']
    assert t['requested_mode'] in MODES.values()
    expected = t['requested_mode']
    if x % 2:
        expected = 0
    elif expected >= 2 and not check['symmetry_check_stats']['enabled']:
        expected = 0
    assert t['selected_mode'] == expected
    assert t['shape_fallback'] == int(t['requested_mode'] != 0 and x % 2 != 0)
    assert t['symmetry_fallback'] == int(not x % 2 and t['requested_mode'] >= 2 and not check['symmetry_check_stats']['enabled'])
    slices = (1+y+y*(y-1)//2)*((equations+63)//64)
    full = slices*x*(1 << (x-1))
    assert t['slices'] == slices and t['full_xors'] == full
    assert t['word_bits'] == (32 if equations <= 32 else 64)
    xors, copies = recursive_counts(x//2) if expected >= 2 else (x*(1 << (x-1)), 0)
    assert t['actual_xors'] == slices*xors == check['stats']['transform_xors']
    assert t['mirror_words'] == slices*copies
    if audit is not None:
        assert t['audit_words'] == ((1 << x)*slices if audit and expected else 0)
    if t['audit_words']:
        assert t['audit_words'] == (1 << x)*slices
        assert t['audit_bytes'] == t['audit_words']*(t['word_bits']//8)
        assert t['audit_xors'] == full
    else:
        assert t['audit_bytes'] == t['audit_xors'] == 0
