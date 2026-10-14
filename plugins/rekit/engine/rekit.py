#!/usr/bin/env python3
"""Entry point: python3 rekit.py <command> ...  (see `python3 rekit.py -h`)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rekit.cli import main
main()
