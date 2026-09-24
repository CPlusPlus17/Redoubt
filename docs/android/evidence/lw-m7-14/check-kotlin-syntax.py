#!/usr/bin/env python3
"""Parse Kotlin source with PSI. This is not target compilation or test execution."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kotlin-cache', type=Path, required=True, help='Gradle modules-2/files-2.1 directory')
parser.add_argument('files', nargs='+', type=Path)
args = parser.parse_args()
artifacts = [('org.jetbrains.kotlin', name, '2.3.10') for name in
             ['kotlin-compiler-embeddable', 'kotlin-stdlib', 'kotlin-script-runtime', 'kotlin-daemon-embeddable']]
artifacts += [('org.jetbrains.kotlin', 'kotlin-reflect', '1.6.10'),
              ('org.jetbrains.kotlinx', 'kotlinx-coroutines-core-jvm', '1.8.0')]
jars = []
for group, artifact, version in artifacts:
    matches = list((args.kotlin_cache/group/artifact/version).rglob('*.jar'))
    if not matches:
        parser.error(f'Missing cached compiler dependency: {group}:{artifact}:{version}')
    jars.extend(matches)
classpath = ':'.join(map(str, jars))
helper = Path(__file__).with_name('KotlinSyntax.java')
with tempfile.TemporaryDirectory(prefix='lw-m7-14-kotlin-psi-') as work:
    subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-cp', classpath,
                    '-d', work, str(helper)], check=True)
    result = subprocess.run(['java', '-Xmx1g', '-cp', work+':'+classpath, 'KotlinSyntax',
                             *map(lambda p: str(p.resolve()), args.files)])
    raise SystemExit(result.returncode)
