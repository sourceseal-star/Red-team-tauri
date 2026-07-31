#!/usr/bin/env python3
"""Test runner for all Red Team modules."""
import unittest
import sys
import os
from pathlib import Path

def discover_and_run():
    base_dir = Path(__file__).parent
    test_files = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.startswith('test_') and f.endswith('.py'):
                test_files.append(os.path.join(root, f))
    print(f'Found {len(test_files)} test files:')
    for tf in sorted(test_files):
        print(f'  {os.path.relpath(tf, base_dir)}')
    print()
    for tf in test_files:
        mod_dir = os.path.dirname(tf)
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for tf in sorted(test_files):
        mod_name = os.path.basename(tf)[:-3]
        try:
            mod = __import__(mod_name)
            suite.addTests(loader.loadTestsFromModule(mod))
        except Exception as e:
            print(f'WARNING: Could not load {mod_name}: {e}')
    verbosity = 2 if '--verbose' in sys.argv else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(discover_and_run())
