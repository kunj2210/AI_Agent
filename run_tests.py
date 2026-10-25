"""
run_tests.py — Root test runner entry point.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "support-agent"))

from tests.run_tests import run_tests

if __name__ == "__main__":
    run_tests()
