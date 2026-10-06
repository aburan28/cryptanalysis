"""Use the unchanged recoverable journal format from round26."""
import sys
from pathlib import Path
_path = sys.path[:]
try:
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'round26'))
    from replay_journal import Journal, recover, encode
finally:
    sys.path[:] = _path
