#!/usr/bin/env python3
"""Source-bound cookie controls checks; target UI, Gecko storage and lifecycle gates are separate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/android/evidence/lw-m7-23'
FENIX = 'mobile/android/fenix/app/src/'
KOTLIN = FENIX + 'main/java/org/mozilla/fenix/'
CONTROLLER = KOTLIN + 'settings/cookiebannerhandling/CookieBannerSiteController.kt'
CONTROLLER_TEST = FENIX + 'test/java/org/mozilla/fenix/settings/cookiebannerhandling/CookieBannerSiteControllerTest.kt'
CONCEPT = 'mobile/android/android-components/components/concept/engine/src/main/java/mozilla/components/concept/engine/'
BRIDGE = 'mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def kotlin_tests(source, cache, scratch):
    """Compile the real controller and its checked-in JUnit tests, with actual
    concept-storage interface and verbatim enum; only EngineSession's unrelated
    body is omitted. No Android UI or native storage is being compiled here.
    All tool dependencies must already exist in the supplied Gradle cache.
    """
    def jar(group, artifact, version):
        paths = list((cache / group / artifact / version).glob('*/*.jar'))
        assert len(paths) == 1, f'Expected one cached jar: {group}:{artifact}:{version}'
        return paths[0]
    jars = [jar(*item) for item in [
        ('org.jetbrains.kotlin', 'kotlin-compiler-embeddable', '2.3.21'),
        ('org.jetbrains.kotlin', 'kotlin-stdlib', '2.3.21'),
        ('org.jetbrains.kotlin', 'kotlin-reflect', '2.3.21'),
        ('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.11.0'),
        ('org.jetbrains.kotlinx', 'kotlinx-coroutines-test-jvm', '1.11.0'),
        ('org.jetbrains', 'annotations', '23.0.0'),
        ('junit', 'junit', '4.13.2'),
        ('org.hamcrest', 'hamcrest-core', '1.3'),
        ('net.bytebuddy', 'byte-buddy', '1.18.2'),
        ('net.bytebuddy', 'byte-buddy-agent', '1.18.2'),
        ('org.objenesis', 'objenesis', '3.4'),
    ]]
    for artifact in ('mockk-jvm', 'mockk-agent-jvm', 'mockk-agent-api-jvm', 'mockk-dsl-jvm', 'mockk-core-jvm'):
        jars.append(jar('io.mockk', artifact, '1.14.11'))
    cp = os.pathsep.join(map(str, jars))
    original = (source / (CONCEPT + 'EngineSession.kt')).read_text()
    enum = re.search(r'    enum class CookieBannerHandlingMode\(val mode: Int\) \{.*?\n    }', original, re.S)
    assert enum
    enum_file = scratch / 'EngineSession.kt'
    enum_file.write_text('package mozilla.components.concept.engine\nclass EngineSession {\n' + enum[0] + '\n}\n')
    output = scratch / 'kotlin-classes'
    subprocess.run(['java', '-cp', cp, 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-no-stdlib', '-no-reflect',
                    '-Werror', '-classpath', cp, '-d', str(output), str(enum_file),
                    str(source / (CONCEPT + 'cookiehandling/CookieBannersStorage.kt')),
                    str(source / CONTROLLER), str(source / CONTROLLER_TEST)], check=True)
    subprocess.run(['java', '-cp', str(output) + os.pathsep + cp, 'org.junit.runner.JUnitCore',
                    'org.mozilla.fenix.settings.cookiebannerhandling.CookieBannerSiteControllerTest'], check=True)
    print('PASS actual Kotlin controller compiled with -Werror and its 16 JUnit tests; Android UI/storage tests remain target gates', flush=True)


def checks(source):
    strings = ET.parse(source / (FENIX + 'main/res/values/strings.xml')).getroot()
    values = {item.attrib['name']: item.text for item in strings if item.tag == 'string'}
    assert values['preferences_cookie_banner_reduction_normal_mode'] == 'Cookie Banner Blocker in normal browsing'
    assert 'HTTP and HTTPS' in values['cookie_banner_site_scope'] and 'subdomains' in values['cookie_banner_site_scope']
    assert 'last private tab' in values['cookie_banner_site_private']
    assert 'Not every banner' in values['cookie_banner_site_on']
    ids = ET.parse(source / (FENIX + 'main/res/values/cookie_banner_controls_ids.xml')).getroot()
    assert {e.attrib['name'] for e in ids} == {
        'cookie_banner_site_controls', 'cookie_banner_site_switch', 'cookie_banner_site_reset',
        'cookie_banner_site_status', 'cookie_banner_site_scope',
    }
    prefs = ET.parse(source / (FENIX + 'main/res/xml/preferences.xml')).getroot()
    android = '{http://schemas.android.com/apk/res/android}'
    rows = {e.attrib.get(android + 'key'): e for e in prefs.iter()}
    normal = rows['@string/pref_key_cookie_banner_normal_mode']
    assert normal.tag == 'androidx.preference.SwitchPreferenceCompat'
    assert normal.attrib[android + 'defaultValue'] == 'true'
    assert '@string/pref_key_cookie_banner_private_mode' in rows
    for name in ['CookieBannerSiteController.kt', 'CookieBannerSiteDialogFragment.kt']:
        text = (source / (KOTLIN + 'settings/cookiebannerhandling/' + name)).read_text()
        assert 'clearData(' not in text and 'addPersistentExceptionInPrivateMode(' not in text
    legacy = (source / (KOTLIN + 'settings/quicksettings/protections/cookiebanners/CookieBannerDetailsController.kt')).read_text()
    assert 'clearSiteData(' not in legacy and 'clearData(' not in legacy
    adapter = (source / (KOTLIN + 'settings/quicksettings/protections/cookiebanners/CookieBannerPanelDialogFragment.kt')).read_text()
    assert 'CookieBannerPanelDialogFragment : CookieBannerSiteDialogFragment()' in adapter
    print('PASS parsed XML, stable controls/scope labels, legacy safe route and absence of implicit data clearing', flush=True)
    subprocess.run(['node', '--check', str(source / BRIDGE)], check=True)
    subprocess.run(['node', str(ROOT / 'scripts/tests/test-cookie-banner-controls.js'), str(source)], check=True)
    subprocess.run(['node', '--check', str(source / 'toolkit/components/cookiebanners/test/unit/test_cookiebanner_private_session.js')], check=True)
    subprocess.run(['python3', str(EVIDENCE / 'test-native-fence.py'), str(source)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Check this already patched source instead of replaying archived originals')
    parser.add_argument('--kotlin-cache', type=Path, help='Existing Gradle modules-2/files-2.1 cache for compiling/running the actual controller JUnit tests')
    args = parser.parse_args()
    inventory = json.loads((EVIDENCE / 'source-files.json').read_text())
    with tempfile.TemporaryDirectory(prefix='lw23-check-') as tmp:
        scratch = Path(tmp)
        source = args.source.resolve() if args.source else scratch / 'source'
        if not args.source:
            source.mkdir()
            expected = {item['path']: item for item in inventory['files'] if item['before_sha256'] is not None}
            with tarfile.open(EVIDENCE / 'source-baseline.tar.gz') as archive:
                assert {m.name for m in archive.getmembers()} == set(expected)
                for member in archive.getmembers():
                    assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
                    data = archive.extractfile(member).read()
                    assert sha(data) == expected[member.name]['before_sha256'], member.name
                    target = source / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(ROOT / 'patches/android/cookie-banner-controls.patch')],
                                    cwd=source, text=True, capture_output=True, check=True)
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout
            print('PASS archive inputs verified and patch applies with zero fuzz/offset', flush=True)
        for entry in inventory['files']:
            assert sha((source / entry['path']).read_bytes()) == entry['after_sha256'], entry['path']
        print('PASS all reconstructed source hashes', flush=True)
        checks(source)
        if args.kotlin_cache:
            kotlin_tests(source, args.kotlin_cache.resolve(), scratch)
        else:
            print('NOT RUN standalone Kotlin JUnit gate: provide --kotlin-cache; target build/full Fenix/runtime also remain required')


if __name__ == '__main__':
    main()
