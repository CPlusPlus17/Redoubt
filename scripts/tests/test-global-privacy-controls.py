#!/usr/bin/env python3
"""Execute actual-module host tests against the independently replayed candidate."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / 'docs/android/evidence/lw-m7-36/check-source.py'
spec = importlib.util.spec_from_file_location('global_privacy_source', CHECK)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
ANDROID = '{http://schemas.android.com/apk/res/android}'


def main():
    source.verify_originals()
    with tempfile.TemporaryDirectory(prefix='lw-m7-36-host-') as directory:
        tree = Path(directory)
        source.replay(tree)
        shared = tree / 'mobile/shared/components/geckoview'
        subprocess.run(['node', str(ROOT / 'scripts/tests/test-global-privacy-controls.js'), str(shared / 'GeckoViewGlobalPrivacy.sys.mjs')], check=True)
        startup = (shared / 'GeckoViewStartup.sys.mjs').read_text()
        source.require('GeckoViewGlobalPrivacy.sys.mjs' in startup and 'GeckoView:GlobalPrivacy:Operation' in startup, 'native event registration missing')
        source.require('"GeckoViewGlobalPrivacy.sys.mjs"' in (shared / 'moz.build').read_text(), 'native module packaging missing')
        res = tree / 'mobile/android/fenix/app/src/main/res'
        screen = ET.parse(res / 'xml/global_privacy_settings.xml').getroot()
        controls = {node.get(ANDROID + 'key'): node for node in screen.iter() if node.get(ANDROID + 'key')}
        for key in ['rfp', 'webglPrompt', 'webglHide', 'disableIPv6', 'referrerPolicy']:
            source.require(key in controls and controls[key].get(ANDROID + 'persistent') == 'false', 'control would use local persistence: ' + key)
        for relative in ['values/global_privacy_controls.xml', 'navigation/nav_graph.xml', 'xml/preferences.xml']:
            ET.parse(res / relative)
        resources = ET.parse(res / 'values/global_privacy_controls.xml').getroot()
        values = next(node for node in resources if node.get('name') == 'global_privacy_referrer_values')
        source.require([node.text for node in values] == ['0', '1', '2'], 'middle native referrer value lost')
        nav = (res / 'navigation/nav_graph.xml').read_text()
        source.require('org.mozilla.fenix.settings.GlobalPrivacySettingsFragment' in nav, 'screen destination missing')
    print('INTEGRATION SOURCE CHECKS PASS: native registration/packaging, nonpersistent controls, XML resources and enum0/1/2.')
    print('HOST ONLY: target C++/Java/Kotlin compilation, native/GV/Fenix suites and APK behavior remain unrun.')


if __name__ == '__main__':
    main()
