"""Pure result handling shared by Modal benchmarks and local regression tests."""
import math
import re
import statistics


def parseRate(text):
    """Only accept a finite, positive rate from a completed run."""
    matches = re.findall(r'^\s*finished:\s+(\S+) M it/s,', text, re.MULTILINE)
    if len(matches) != 1:
        return 0.0
    try:
        rate = float(matches[0])
    except ValueError:
        return 0.0
    return rate if math.isfinite(rate) and rate > 0 else 0.0


def benchResult(command, returncode, output):
    rate = parseRate(output)
    valid = returncode == 0 and rate > 0 and 'MISMATCH' not in output and 'stopping:' not in output
    result = dict(command=command, returncode=returncode, raw=output,
                  valid=valid, rate=rate if valid else 0.0)
    if not valid:
        result['error'] = 'benchmark failed, was interrupted, or lacks a valid final rate'
    return result


def summarizeSamples(samples):
    valid = bool(samples) and all(s['valid'] for s in samples)
    if not valid:
        return dict(valid=False, rate=0.0, samples=samples,
                    error='one or more benchmark repetitions failed')
    rates = [s['rate'] for s in samples]
    return dict(valid=True, rate=statistics.median(rates),
                minRate=min(rates), maxRate=max(rates), samples=samples)


def bestResult(results):
    valid = [r for r in results if r.get('valid', False)]
    return max(valid, key=lambda r: r['rate']) if valid else None


def reportsVerified(returncode, output, required=16):
    """A report-replay gate must actually verify reports and lose none."""
    if returncode or 'MISMATCH' in output or 'stopping:' in output:
        return False
    matches = re.findall(
        r'finished:.*?, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)',
        output)
    return (len(matches) == 1 and int(matches[0][0]) >= required
            and int(matches[0][1]) >= required and int(matches[0][2]) == 0)
