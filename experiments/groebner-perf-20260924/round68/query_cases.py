"""Frozen validation arm matrix and accounting contract; no arithmetic or native loading."""
MODES = ('cpu', 'metal', 'metal_tiled')


def query_modes(available):
    modes = [('cpu', 'cpu', sanitizer, 'cpu') for sanitizer in (False, True)]
    if available:
        modes += [('metal', checker, sanitizer, transform)
                  for checker in ('cpu', 'metal_simd') for sanitizer in (False, True)
                  for transform in MODES]
    return modes


def check_accounting(answer, item, backend, transform):
    stats = answer['producer_transform_stats']
    mode = MODES.index(transform)
    compatible = backend == 'metal' and item['n'] <= 32
    assert not mode or compatible
    assert stats['requested_mode'] == stats['executed_mode'] == mode
    assert stats['additional_table_bytes'] == 0
    size = (1 << (2 * item['ell'])) * (1 + item['ell'] * (item['ell'] + 1) // 2) * 4
    kernel = stats['kernel']
    assert stats['projection_uploaded_bytes'] == (size if compatible and not mode else 0)
    assert stats['projection_reused_bytes'] == (size if mode else 0)
    assert kernel['input_bytes'] == kernel['output_bytes'] == kernel['scratch_bytes'] == (size if mode else 0)
    if compatible: assert stats['generation'] > 0
    else: assert stats['generation'] == 0
    if mode:
        x = 2 * item['ell']
        dispatches = x if mode == 1 else 1 + x - min(x, 4)
        assert kernel['encoded_dispatches'] == kernel['submitted_dispatches'] == kernel['completed_dispatches'] == dispatches
        assert kernel['logical_xors'] == x * size // 8
        assert kernel['wall'] >= sum(kernel[key] for key in ('copy_in', 'encode', 'wait', 'copy_out'))
        assert 0 <= kernel['wall'] <= answer['metrics']['specialization']
    else:
        assert all(value == 0 for value in kernel.values())
