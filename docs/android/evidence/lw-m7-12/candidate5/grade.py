#!/usr/bin/env python3
"""Grade candidate5 unit XML; native instrumentation and APK behavior stay separate."""
import argparse
import importlib.util
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prior_unit_grade', HERE.parent / 'grade-extended-tests.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def suites(inventory):
    result = {key: {'relative': path, 'minimum_classes': classes, 'minimum_tests': tests,
                    'required': set(required), 'methods': {}, 'class_counts': {}}
              for key, (path, classes, tests, required) in prior.SUITES.items()}
    result['addons'] = {'relative': 'android-components/components/feature/addons',
                        'minimum_classes': 0, 'minimum_tests': 0, 'required': set(), 'methods': {}, 'class_counts': {}}
    for row in inventory['tests']:
        suite = result[row['suite']]
        if row['class'] not in suite['required']:
            suite['minimum_classes'] += 1
        suite['required'].add(row['class'])
        suite['methods'][row['class']] = row['required_methods']
        suite['class_counts'][row['class']] = row['declared_test_count']
    return result


def inspect(directory, started, ended, suite, allow_failures):
    result = prior.inspect_suite(directory, started, suite['required'], suite['minimum_classes'],
                                 suite['minimum_tests'], allow_failures)
    seen = set()
    methods = {}
    for path in sorted(directory.glob('TEST-*.xml')):
        if path.stat().st_mtime > ended:
            result['issues'].append(path.name + ': XML changed after test completion')
        root = ET.parse(path).getroot()
        name = root.get('name')
        methods[name] = []
        for case in root.findall('testcase'):
            identity = (case.get('classname'), case.get('name'))
            if not all(identity) or identity in seen or identity[0] != name:
                result['issues'].append(path.name + ': inconsistent/duplicate testcase identity')
            seen.add(identity)
            methods[name].append(case.get('name', ''))
    for klass, count in suite.get('class_counts', {}).items():
        if len(methods.get(klass, [])) < count:
            result['issues'].append(klass + ': truncated class test count')
    for klass, required in suite['methods'].items():
        actual = methods.get(klass, [])
        for method in required:
            if not any(case == method or case.startswith(method + '[') for case in actual):
                result['issues'].append(klass + ': required method missing: ' + method)
    return result


def grade(root, evidence, inventory):
    started = float((evidence / 'started-epoch.txt').read_text())
    ended = float((evidence / 'tests-ended-epoch.txt').read_text())
    if ended < started:
        raise ValueError('test times reversed')
    results = {}
    for key, suite in suites(inventory).items():
        directory = root / suite['relative'] / 'test-results/testDebugUnitTest'
        with tarfile.open(evidence / (key + '-junit-xml.tar.gz'), 'w:gz') as archive:
            for path in sorted(directory.glob('TEST-*.xml')):
                archive.add(path, arcname=path.name, recursive=False)
        results[key] = inspect(directory, started, ended, suite, key == 'fenix')
    (evidence / 'junit-summary.json').write_text(json.dumps(results, indent=2) + '\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    inventory = json.loads((HERE / 'unit-inventory.json').read_text())
    result = grade(args.results, args.evidence, inventory)
    print(json.dumps({key: {k: v for k, v in row.items() if k != 'classes'}
                      for key, row in result.items()}, indent=2))
    if any(row['issues'] for row in result.values()):
        return 1
    print('PASS fresh full/targeted Gradle XML and all required feature methods; Fenix allowance gate remains separate')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
