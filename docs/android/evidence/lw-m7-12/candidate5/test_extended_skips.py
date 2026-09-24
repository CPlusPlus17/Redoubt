"""A required complete component suite cannot pass by skipping a case."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('extended_skip_gate',
    Path(__file__).resolve().parents[1] / 'grade-extended-tests.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class ComponentSkipTests(unittest.TestCase):
    def test_support_extension_skip_is_rejected_without_named_required_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / 'TEST-component.xml'
            path.write_text('<testsuite name="component" tests="2" failures="0" errors="0" skipped="1">'
                            '<testcase name="passed"/><testcase name="skipped"><skipped/></testcase></testsuite>')
            result = g.inspect_suite(directory, 0, set(), 1, 2)
            self.assertIn('component: unexpected target failure/error/skip', result['issues'])
            path.write_text('<testsuite name="component" tests="2" failures="0" errors="0" skipped="0">'
                            '<testcase name="first"/><testcase name="second"/></testsuite>')
            self.assertFalse(g.inspect_suite(directory, 0, set(), 1, 2)['issues'])


if __name__ == '__main__':
    unittest.main()
