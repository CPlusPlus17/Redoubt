from pathlib import Path
import hashlib,json,tarfile,io,subprocess,os,shutil,zipfile,datetime
work=Path('/home/runner/work/feature-parity-20260908');os.chdir(work/'repo');os.environ['XDG_RUNTIME_DIR']='/run/user/1001'
sha=lambda p: hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
native=work/'evidence/parity-extended-native'
assert (native/'build-exit.txt').read_text().strip()=='1'
assert sha(native/'source-sha256.txt')=='4756b69d2f016997221f44c31a8213535a01b68e44e467b7ee5987d209e345c2'
assert not subprocess.check_output(['podman','ps','-q'],text=True).strip()
for line in (native/'source-sha256.txt').read_text().splitlines():
 digest,name=line.split('  ',1);assert sha(work/'src'/name)==digest
capture={};add=lambda name,p: capture.update({name:p.read_bytes()})
for p in native.iterdir():
 if p.is_file():add('driver/'+p.name,p)
for p in (work/'aar/logs').iterdir():
 if p.is_file():add('logs/'+p.name,p)
add('build-times.txt',work/'aar/build-times.txt')
for name in ['scripts/android-fat-aar.sh','assets/mozconfig.android','docs/android/evidence/lw-m7-25/podman-native-bounded.sh','docs/android/evidence/lw-m7-12/run-extended-native.sh']:
 add('configuration/'+name,work/'repo'/name)
unit='redoubt-parity-native4-20260909.service'
capture['service.txt']=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','-p','ExecMainStatus','-p','InvocationID','-p','ExecMainStartTimestamp','-p','ExecMainExitTimestamp'])
capture['journal.txt']=subprocess.check_output(['journalctl','--user','--no-pager','-u',unit])
add('memory-events.txt',Path('/sys/fs/cgroup/user.slice/user-1001.slice/memory.events'))
artifacts=work/'native4-packaging-failure-artifacts';artifacts.mkdir()
rows={}
for abi in ['armeabi-v7a','arm64-v8a','x86_64']:
 original=work/'aar'/abi/'target.maven.zip';retained=artifacts/abi/'target.maven.zip';retained.parent.mkdir();shutil.copy2(original,retained);assert sha(retained)==sha(original)
 with zipfile.ZipFile(original) as z:aars=[n for n in z.namelist() if n.endswith('.aar')]
 rows[abi]={'sha256':sha(original),'bytes':original.stat().st_size,'retained':str(retained),'aars':aars}
 assert 'MACH_EXIT=0' in (work/'aar/logs'/f'{abi}.log').read_text()
 profiles=sorted((work/'src'/f'obj-{abi}'/'.mozbuild/logs/build').glob('profile_log_*.json'))
 if profiles:add('profiles/'+abi+'-'+profiles[-1].name,profiles[-1])
result={'classification':'All three ABI compilations passed; x86_64 Maven packaging failed on two AARs; merge/APK/tests/runtime did not run.','invocation':'367f4a0c473843b4832ee42f0c9e2ff2','source_count':164,'source_manifest_sha256':sha(native/'source-sha256.txt'),'driver_exit':1,'artifacts':rows,'captured':datetime.datetime.now(datetime.timezone.utc).isoformat()}
capture['result.json']=(json.dumps(result,indent=2)+'\n').encode()
with tarfile.open(fileobj=__import__('sys').stdout.buffer,mode='w|gz') as t:
 for name,data in capture.items():
  m=tarfile.TarInfo(name);m.size=len(data);t.addfile(m,io.BytesIO(data))
