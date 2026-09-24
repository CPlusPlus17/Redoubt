#!/usr/bin/env python3
"""Require fresh complete target results in addition to the Fenix allowance gate."""
import json
from pathlib import Path
import sys
import tarfile
import xml.etree.ElementTree as ET

SUITES = {
    'fenix': ('fenix/app', 602, 5468, {
        'org.mozilla.fenix.FenixApplicationTest',
        'org.mozilla.fenix.HomeActivityAccountSettingsTest',
        'org.mozilla.fenix.customtabs.ExternalAppBrowserActivityTest',
        'org.mozilla.fenix.settings.account.AuthCustomTabActivityTest',
        'org.mozilla.fenix.settings.creditcards.CreditCardItemViewHolderTest',
        'org.mozilla.fenix.browser.permissions.OriginBoundPermissionsFeatureTest',
        'org.mozilla.fenix.browser.permissions.OriginBoundPermissionsDialogFragmentTest',
        'org.mozilla.fenix.utils.HomeSectionDefaultsTest',
        'org.mozilla.fenix.settings.AccountServicesPreferenceTest',
        'org.mozilla.fenix.settings.cookiebannerhandling.CookieBannerSettingsTest',
        'org.mozilla.fenix.settings.cookiebannerhandling.CookieBannerSiteControllerTest',
        'org.mozilla.fenix.settings.quicksettings.ProtectionsViewTest',
        'org.mozilla.fenix.settings.quicksettings.protections.cookiebanners.DefaultCookieBannerDetailsControllerTest',
        'org.mozilla.fenix.settings.search.FirefoxSuggestPolicyTest',
    }),
    'extensions': ('android-components/components/support/webextensions', 4, 53, set()),
    'gecko': ('android-components/components/browser/engine-gecko', 4, 4, {
        'mozilla.components.browser.engine.gecko.permission.OriginBoundPermissionRequestTest',
        'mozilla.components.browser.engine.gecko.permission.OriginBoundPermissionsStorageTest',
        'mozilla.components.browser.engine.gecko.permission.GeckoSitePermissionsStorageTest',
        'mozilla.components.browser.engine.gecko.cookiebanners.GeckoCookieBannersStorageTest',
    }),
    'state': ('android-components/components/browser/state', 1, 1, {
        'mozilla.components.browser.state.ext.PermissionRequestTest',
    }),
    'accounts': ('android-components/components/service/firefox-accounts', 3, 19, {
        'mozilla.components.service.fxa.AccountServicesDisabledTest',
        'mozilla.components.service.fxa.AccountServicesTest',
        'mozilla.components.service.fxa.sync.AccountServicesWorkerTest',
    }),
    'syncedtabs': ('android-components/components/feature/syncedtabs', 1, 1, {
        'mozilla.components.feature.syncedtabs.commands.AccountServicesFlushWorkerTest',
    }),
    'suggest': ('android-components/components/feature/fxsuggest', 2, 14, {
        'mozilla.components.feature.fxsuggest.FxSuggestAdmissionTest',
        'mozilla.components.feature.fxsuggest.datasource.OnlineSuggestionAdmissionTest',
    }),
}

def inspect_suite(directory, started, required, minimum_classes, minimum_tests, allow_failures=False):
    files = sorted(directory.glob('TEST-*.xml'))
    rows, issues = [], []
    names = set()
    for path in files:
        if path.stat().st_mtime < started:
            issues.append(f'{path.name}: stale XML')
        tree = ET.parse(path).getroot()
        name = tree.get('name', '')
        if not name or name in names:
            issues.append(f'{path.name}: missing/duplicate suite identity')
        names.add(name)
        cases = tree.findall('testcase')
        row = {'name': name, 'tests': len(cases),
               'failures': sum(case.find('failure') is not None for case in cases),
               'errors': sum(case.find('error') is not None for case in cases),
               'skipped': sum(case.find('skipped') is not None for case in cases)}
        for field in ('tests', 'failures', 'errors', 'skipped'):
            if int(tree.get(field, 0)) != row[field]:
                issues.append(f'{name}: inconsistent {field} count')
        if name in required and (not row['tests'] or any(row[key] for key in ('failures', 'errors', 'skipped'))):
            issues.append(f'{name}: a required feature class did not fully pass')
        if not allow_failures and (row['failures'] or row['errors'] or row['skipped']):
            issues.append(f'{name}: unexpected target failure/error/skip')
        rows.append(row)
    if len(rows) < minimum_classes or sum(row['tests'] for row in rows) < minimum_tests:
        issues.append('Missing or truncated target suite')
    if required - names:
        issues.append('Required feature classes missing: ' + ', '.join(sorted(required - names)))
    summary = {'classes': len(rows), **{
        field: sum(row[field] for row in rows) for field in ('tests', 'failures', 'errors', 'skipped')
    }}
    return {'summary': summary, 'issues': issues, 'classes': rows}

def main():
    root, evidence = map(Path, sys.argv[1:])
    started = float((evidence / 'started-epoch.txt').read_text())
    output = {}
    for name, (relative, classes, tests, required) in SUITES.items():
        directory = root / relative / 'test-results/testDebugUnitTest'
        with tarfile.open(evidence / f'{name}-junit-xml.tar.gz', 'w:gz') as archive:
            for path in sorted(directory.glob('TEST-*.xml')):
                archive.add(path, arcname=path.name, recursive=False)
        output[name] = inspect_suite(directory, started, required, classes, tests, name == 'fenix')
    (evidence / 'junit-summary.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({name: {key: value for key, value in result.items() if key != 'classes'}
                      for name, result in output.items()}, indent=2))
    if any(result['issues'] for result in output.values()):
        raise SystemExit(1)
    print('PASS fresh target XML and required feature classes; Fenix allowance gate is separate')

if __name__ == '__main__':
    main()
