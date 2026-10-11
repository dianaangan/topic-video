"""Launch with either installed requirements or checkout-local packages."""
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).parent/'.packages'))
runpy.run_module('server', run_name='__main__')
