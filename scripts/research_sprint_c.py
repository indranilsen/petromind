#!/usr/bin/env python3
"""Isolated Sprint C CLI; MODEL_API_KEY is read only by trusted HTTP transport."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.sprint_c.runner import main
if __name__=='__main__':main()
