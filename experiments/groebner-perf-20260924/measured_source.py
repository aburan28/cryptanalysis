"""Read exact historical source bytes without substituting them into live code."""
import gzip
import hashlib
from pathlib import Path
import re

ARCHIVE = Path(__file__).resolve().parent / 'measured_sources'


def measured_bytes(path, expected):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('invalid source digest')
    current = Path(path).read_bytes()
    if hashlib.sha256(current).hexdigest() == expected:
        return current
    # Only explicitly retained versions can satisfy an old measurement receipt.
    # This function never imports, executes, or installs the archived source.
    frozen = gzip.decompress((ARCHIVE / (expected + '.gz')).read_bytes())
    if hashlib.sha256(frozen).hexdigest() != expected:
        raise ValueError('corrupt measured-source archive: ' + expected)
    return frozen
