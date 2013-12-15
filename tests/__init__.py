# should import all others and run all on main

import unittest
import os, sys

if __name__ == '__main__':
    test_paths = sys.argv[1:]
    cwd = os.path.dirname(os.path.realpath(__file__))
    test_paths = test_paths or [cwd]

    suites = unittest.TestSuite()
    for test_path in test_paths:
        # tests/ directory
        if os.path.isdir(test_path):
            suite = unittest.loader.TestLoader().discover(test_path)
            suites.addTest(suite)
            suite = unittest.loader.TestLoader().discover(test_path, pattern='*test.py')
            suites.addTest(suite)
        # test_file.py
        elif os.path.isfile(test_path):
            test_path, test_file = test_path.rsplit(os.path.sep, 1)
            suite = unittest.loader.TestLoader().discover(test_path, test_file)
            suites.addTest(suite)
        # tests.module.TestCase
        elif '/' not in test_path and '.' in test_path:
            suite = unittest.loader.TestLoader().loadTestsFromName(test_path)
            suites.addTest(suite)
    unittest.TextTestRunner(verbosity=2).run(suites)

