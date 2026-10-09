import types, os, sys, json, time
src=open(os.path.expanduser('~/redoubt-artifacts/sec-parity/repo/scripts/android-smoke.sh')).read()
src=src.split("<<'PYDRIVEREOF'\n",1)[1].split('\nPYDRIVEREOF',1)[0]
h=types.ModuleType('d'); exec(compile(src,'d','exec'),h.__dict__)
adb=h.Adb(os.path.expanduser('~/redoubt-artifacts/sec-parity/sdk34/platform-tools/adb'),'emulator-5584')
app=h.App(adb,'org.redoubtbrowser',os.path.expanduser('~/redoubt-artifacts/sec-parity/work'))
