import io,tarfile,subprocess,os,sys
from pathlib import Path
work=Path('/home/runner/work/feature-parity-20260908'); os.environ['XDG_RUNTIME_DIR']='/run/user/1001'
unit='redoubt-fenix-navigation-diagnostic-20260909.service'
service=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','-p','SubState','-p','ExecMainStatus','-p','InvocationID','-p','ExecMainStartTimestamp','-p','ExecMainExitTimestamp'])
assert b'InvocationID=aea186042c534419b68a50f030c53f0e' in service and b'SubState=exited' in service and b'ExecMainStatus=0' in service
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
    for folder in ['fenix-navigation-diagnostic-20260909','fenix-navigation-fixture-source']:
        for p in (work/'evidence'/folder).iterdir():
            if p.is_file():t.add(p,arcname=folder+'/'+p.name,recursive=False)
    for name,data in [('service.txt',service),('journal.txt',subprocess.check_output(['journalctl','--user','--no-pager','-u',unit]))]:
        member=tarfile.TarInfo(name);member.size=len(data);t.addfile(member,io.BytesIO(data))
