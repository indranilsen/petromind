#!/usr/bin/env python3
"""Owner-reviewed, local-only Sprint C continuation. No credentials in arguments."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.sprint_c.recovery.workflow import main
if __name__=='__main__':main()
