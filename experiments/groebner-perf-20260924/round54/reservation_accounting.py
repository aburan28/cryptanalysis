"""Exact row reservation accounting, including exception and budget exits."""
def reservation_accounting(answer, enabled):
    stats, partial = answer['partial_reservation_stats'], answer['partial_stats']
    assert stats['mode'] == int(enabled)
    if not enabled:
        assert all(value == 0 for name, value in stats.items() if name != 'mode')
        return
    assert stats['reservation_attempts'] == stats['reserved_rows'] + stats['budget_fallbacks']
    assert stats['flushes'] == stats['reserved_rows']
    assert stats['exception_flushes'] <= stats['flushes']
    assert stats['parity_words'] <= stats['charged_words'] <= partial['work']
    assert stats['parity_words'] <= partial['witness_parities']
    assert stats['max_row_words'] <= 112
    if not stats['budget_fallbacks']:
        assert stats['parity_words'] == partial['witness_parities']

