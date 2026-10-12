import unittest
from container_smoke import observer_processes

class ProcessListingTests(unittest.TestCase):
    def test_exact_processes(self):
        found=observer_processes('PID COMMAND\n10 python3 supervise.py\n11 /usr/local/bin/python3 /app/runner.py')
        self.assertEqual(found['runner.py'],[11])
    def test_duplicate_rejected(self):
        with self.assertRaises(AssertionError):observer_processes('PID COMMAND\n10 python3 supervise.py\n11 python3 /app/runner.py\n12 python3 /app/runner.py')
    def test_missing_rejected(self):
        with self.assertRaises(AssertionError):observer_processes('PID COMMAND\n10 python3 supervise.py')
    def test_substring_not_a_script(self):
        with self.assertRaises(AssertionError):observer_processes('PID COMMAND\n10 python3 supervise.py\n11 python3 -c runner.py')
    def test_pid_column_required(self):
        with self.assertRaises(AssertionError):observer_processes('COMMAND\npython3 runner.py')

if __name__=='__main__':unittest.main()
