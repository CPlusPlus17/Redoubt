from pathlib import Path
import hashlib,json,tarfile,sys,io,datetime
root=Path('/home/runner/work/feature-parity-20260908/src')
manifest=Path('/home/runner/work/feature-parity-20260908/evidence/parity-extended-native/source-sha256.txt')
parent=manifest.read_bytes()
rows={line.split('  ',1)[1]:line.split('  ',1)[0] for line in parent.decode().splitlines()}
paths=['mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataController.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataOnQuitFragment.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/settings/deletebrowsingdata/DeleteBrowsingDataOnQuitType.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/menu/MenuDialogFragment.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt', 'mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt', 'mobile/android/android-components/components/browser/engine-gecko/src/main/java/mozilla/components/browser/engine/gecko/GeckoEngine.kt', 'mobile/android/android-components/components/concept/engine/src/main/java/mozilla/components/concept/engine/DataCleanable.kt', 'mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs', 'mobile/android/geckoview/src/main/java/org/mozilla/geckoview/StorageController.java', 'toolkit/components/cleardata/PrincipalsCollector.sys.mjs', 'toolkit/components/cleardata/ClearDataService.sys.mjs', 'toolkit/components/cleardata/nsIClearDataService.idl']
sha=lambda raw:hashlib.sha256(raw).hexdigest()
contents={}; observed={}
for name in paths:
 assert not Path(name).is_absolute() and '..' not in Path(name).parts
 path=root/name
 raw=path.read_bytes() if path.is_file() else None
 observed[name]={'sha256':sha(raw) if raw is not None else None,'in_native_manifest':name in rows}
 if name in rows:assert raw is not None and sha(raw)==rows[name],name
 if raw is not None:contents['source/'+name]=raw
for name,entry in observed.items():
 path=root/name
 assert (sha(path.read_bytes()) if path.is_file() else None)==entry['sha256'],name
assert manifest.read_bytes()==parent
report={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'read-only source subset; no source or build mutation','source':str(root),'native_manifest_sha256':sha(parent),'files':observed}
contents['capture.json']=(json.dumps(report,indent=2)+'\n').encode()
contents['parent-source-sha256.txt']=parent
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for name,raw in contents.items():
  info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o644;archive.addfile(info,io.BytesIO(raw))
