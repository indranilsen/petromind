#!/usr/bin/env python3
"""Isolated research phase; run from a reviewed owner-local checkout."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.sprint_c.phase2.runner import main
if __name__=='__main__':main()
