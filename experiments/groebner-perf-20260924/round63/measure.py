"""Run the unchanged paired-panel driver with this round's frozen context."""
from pathlib import Path
import runpy
import common

shared=runpy.run_path(str(common.P/'round57/measure.py'))
assert shared['HERE']==Path(__file__).resolve().parent
if __name__=='__main__':shared['main']()
