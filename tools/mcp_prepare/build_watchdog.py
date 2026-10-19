"""Compatibility entry: only the selected manual-ACK package is now built."""
from build_manual_ack import build
from pathlib import Path
import sys
if __name__=="__main__":build(Path(sys.argv[1]),Path(sys.argv[2]))
