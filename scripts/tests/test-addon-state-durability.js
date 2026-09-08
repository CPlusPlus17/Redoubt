/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = process.argv[2];
assert.ok(source, 'usage: node test-addon-state-durability.js PATCHED_SOURCE');
const dir = path.join(source, 'toolkit/mozapps/extensions/internal');
const read = name => fs.readFileSync(path.join(dir, name + '.sys.mjs'), 'utf8');
const providerSource = read('XPIProvider');
const databaseSource = read('XPIDatabase');
const installSource = read('XPIInstall');
const slice = (text, start, end) => {
  const a = text.indexOf(start); assert.ok(a >= 0, start);
  const b = text.indexOf(end, a + start.length); assert.ok(b > a, end);
  return text.slice(a, b);
};
const clone = value => JSON.parse(JSON.stringify(value));
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const tick = () => new Promise(resolve => setImmediate(resolve));
const tests = [];
const test = (name, run) => tests.push({name,run});
function fixture(platform='android') {
  const f = {files:new Map(), writes:[], events:[], errors:[], writeGate:null, fail:null, activeWrites:0, maxWrites:0, prefs:new Map(), operations:[]};
  const logger = Object.fromEntries(['debug','warn','error','info'].map(name=>[name,(...args)=>{if(name==='error'||name==='warn')f.errors.push(args);} ]));
  const noop = () => {};
  const gle = new Proxy({}, {get:()=>new Proxy({}, {get:()=>new Proxy({}, {get:()=>noop})})});
  const AddonManager = {SCOPE_ALL:15,SCOPE_PROFILE:1,SCOPE_APPLICATION:4,STATE_INSTALLING:5,STATE_CANCELLED:7,STATE_INSTALLED:6,STATE_INSTALL_FAILED:8,ERROR_FILE_ACCESS:-4};
  const context = vm.createContext({console, DOMException, AppConstants:{platform}, PathUtils:{profileDir:'/profile',join:path.posix.join}, FILE_XPI_STATES:'addonStartup.json.lz4',FILE_JSON_DB:'extensions.json',
    PREF_PENDING_OPERATIONS:'pending',PREF_DB_SCHEMA:'schema',PREF_EM_LAST_APP_BUILD_ID:'build',PREF_EM_STARTUP_SCAN_SCOPES:'scopes',PREF_INSTALL_DISTRO_ADDONS:'distro',KEY_APP_SYSTEM_BUILTINS:'app-builtin-addons',KEY_APP_SYSTEM_ADDONS:'app-system-addons',
    Ci:{nsIFile:{}},DB_SCHEMA:37,logger,SIGNED_TYPES:new Set(["extension"]),Glean:gle,Log:{stackTrace:()=>''},Cu:{reportError:error=>f.errors.push(error)},
    Services:{dirsvc:{get:()=>({path:"/profile"})},prefs:{getBoolPref:(name,value)=>f.prefs.get(name)??value,getIntPref:(name,value)=>f.prefs.get(name)??value,getCharPref:(name,value)=>f.prefs.get(name)??value,setBoolPref:(name,value)=>f.prefs.set(name,value),setIntPref:(name,value)=>f.prefs.set(name,value),setCharPref:(name,value)=>f.prefs.set(name,value)},appinfo:{appBuildID:'build'},policies:null},
    IOUtils:{async writeJSON(file,value,options) {
      const bytes=clone(value); const record={file,bytes,options:clone(options)};f.writes.push(record);f.activeWrites++;f.maxWrites=Math.max(f.maxWrites,f.activeWrites);
      try {if(f.writeGate)await f.writeGate(record); if(f.fail && f.fail(record))throw new Error('disk full');f.files.set(file,bytes);}finally{f.activeWrites--;}
    }},
    lazy:{AddonSettings:{IS_EMBEDDED:true,SCOPES_SIDELOAD:0},AddonManager,AddonManagerPrivate:{callAddonListeners:(name,addon)=>f.events.push({name,id:addon.id,disk:clone([...f.files])}),recordSimpleMeasure:noop},DeferredTask:class {constructor(callback,delay){f.deferred={callback,delay};}arm(){f.armed=true;}async finalize(){}},JSONFile:class {constructor(){f.jsonFile=true;}saveSoon(){f.jsonArmed=true;}}},
    AddonManager,AddonManagerPrivate:{recordSimpleMeasure:noop,callAddonListeners:(name,addon)=>f.events.push({name,id:addon.id,disk:clone([...f.files])})},ASYNC_SAVE_DELAY_MS:20,
    XPIExports:{XPIProvider:{_closing:false},XPIInternal:{DB_SCHEMA:37,BOOTSTRAP_REASONS:{ADDON_ENABLE:1,ADDON_UNINSTALL:2},BootstrapScope:{get:addon=>addon.bootstrap}}},
    canRunInSafeMode:()=>false,
    SystemAddonLocation:{_loadAddonSet:()=>({})},SystemBuiltInLocation:{readAddons:()=>new Map()},
  });
  vm.runInContext(read('AndroidAddonState').replace('export class ','class ')+'\nglobalThis.AndroidAddonState=AndroidAddonState;', context);
  context.lazy.AndroidAddonState=context.AndroidAddonState;
  vm.runInContext(slice(providerSource, 'var XPIStates = {', '\n/**\n * A helper class')+'\nglobalThis.XPIStates=XPIStates;',context);
  vm.runInContext(slice(databaseSource, 'function _filterDB(', '\nexport const XPIDatabase ='),context);
  vm.runInContext(slice(databaseSource, 'export const XPIDatabase = {', '\nexport const XPIDatabaseReconcile =').replace('export const ','var ')+'\nglobalThis.XPIDatabase=XPIDatabase;',context);
  f.context=context;f.states=context.XPIStates;f.db=context.XPIDatabase;context.XPIExports.XPIDatabase=f.db;context.XPIExports.XPIInternal.XPIStates=f.states;
  f.db.initialized=true;f.db.addonDB=new Map();f.db.isUsableAddon=addon=>!addon.unusable;f.db.maybeUpdateBlocklistAttentionAddonIdsSet=noop;f.db.removeFromBlocklistAttentionAddonIdsSet=noop;
  context.PREF_EM_AUTO_DISABLED_SCOPES='autoDisabled';
  f.db.updateAddonActive=function(addon,active){addon.active=active;this.saveChanges();};
  f.addon = (id='test@example.org',enabled=true) => {
    const loc = new Map();Object.assign(loc,{name:'app-profile',isTemporary:false,isSystem:false,scope:1,locked:false,hasStaged:false,toJSON(){return {addons:Object.fromEntries(this)};},removeAddon(id){this.delete(id);f.states.save();},installer:{uninstallAddon(id){f.operations.push('unlink:'+id);}}});
    const addon={id,_key:'app-profile:'+id,type:'extension',inDatabase:true,location:loc,visible:true,active:enabled,userDisabled:!enabled,softDisabled:false,embedderDisabled:false,appDisabled:false,pendingUninstall:false,version:'1',defaultLocale:{name:'Test'},dependencies:[],get disabled(){return this.userDisabled||this.softDisabled||this.appDisabled||this.embedderDisabled;},get wrapper(){return {id:this.id};},toJSON(){return {id,location:loc.name,version:this.version,userDisabled:this.userDisabled,appDisabled:this.appDisabled,embedderDisabled:this.embedderDisabled,active:this.active,pendingUninstall:this.pendingUninstall};}};
    addon.bootstrap={started:enabled,async disable(){if(f.bootstrapGate)await f.bootstrapGate();this.started=false;f.operations.push('disable:'+id);},async startup(){this.started=true;f.operations.push('enable:'+id);},async shutdown(){this.started=false;f.operations.push('shutdown:'+id);},async uninstall(){this.started=false;f.operations.push('uninstall:'+id);}};
    // Execute the actual synchronization method with minimal filesystem boundary.
    const syncSource=slice(providerSource,'  syncWithDB(aDBAddon, aUpdated = false) {','\n}\n\n/**\n * Manages the state');
    const state=vm.runInContext('({'+syncSource+'})',context);
    Object.assign(state,{id,enabled,getModTime:()=>0,getTelemetryKey:()=>id,toJSON(){return {id,enabled:this.enabled,version:this.version};}});
    loc.set(id,state);f.states.db.set(loc.name,loc);f.db.addonDB.set(addon._key,addon);return addon;
  };
  f.install = vm.runInContext('({'+slice(installSource,'  async uninstallAddon(aAddon, aForcePending) {','\n  DirectoryInstaller,')+'})',context);
  context.XPIExports.XPIInstall=f.install;
  f.setUserDisabled=vm.runInContext('({'+slice(databaseSource,'  async setUserDisabled(val, allowSystemAddons = false) {','\n  applyCompatibilityUpdate(')+'})',context).setUserDisabled;
  f.checkForChanges=vm.runInContext('({'+slice(providerSource,'  checkForChanges(aAppChanged, aOldAppVersion, aOldPlatformVersion) {','\n  /**\n   * Gets an array')+'})',context).checkForChanges;
  f.installMethods=vm.runInContext('(class {'+slice(installSource,'  async startInstall() {','\n  /**\n   * Stages an add-on')+'}).prototype',context);
  f.prepareInstall=(old,version='2')=>{
    const addon=Object.defineProperties({},Object.getOwnPropertyDescriptors(old));
    addon.version=version;addon.inDatabase=false;addon._sourceBundle={path:'/extension.xpi'};
    addon.addedToDatabase=function(){this.inDatabase=true;};
    addon.propagateDisabledState=vm.runInContext('({'+slice(databaseSource,'  propagateDisabledState(oldAddon) {','\n}\n\n/**\n * The AddonWrapper')+'})',context).propagateDisabledState;
    const file={path:'/staged.xpi',exists:()=>false,clone(){return this;},append:()=>{}};
    Object.assign(old.location.installer,{getStagingDir:()=>file,requestStagingDir:async()=>{},installAddon:async()=>file,releaseStagingDir:()=>{}});
    old.bootstrap.update=async function(next,active,install){await this.disable();await install();this.started=active;};
    context.XPIExports.XPIProvider.addTelemetry=()=>{};context.flushJarCache=()=>{};
    const install=Object.assign(Object.create(f.installMethods),{addon,existingAddon:old,location:old.location,sourceURI:{spec:'file:///verified.xpi'},file,
      _cleanup:()=>{},removeTemporaryFile:()=>{},unstageInstall:async()=>{},stageInstall:async()=>{},
      _callInstallListeners(name,wrapper){f.events.push({name,id:wrapper?.id,disk:clone([...f.files])});return true;},
    });return install;
  };
  f.diskAddon=id=>f.files.get('/profile/extensions.json')?.addons.find(a=>a.id===id);
  f.diskState=id=>f.files.get('/profile/addonStartup.json.lz4')?.['app-profile']?.addons[id];
  return f;
}

test('one save awaits both writes with flush and separate atomic temp files',async()=>{
  const f=fixture(), addon=f.addon();await f.states.flushAndroid();
  assert.equal(f.diskAddon(addon.id).userDisabled,false);assert.equal(f.diskState(addon.id).enabled,true);
  assert.deepEqual(f.writes.map(r=>r.file),['/profile/extensions.json','/profile/addonStartup.json.lz4']);
  for(const r of f.writes){assert.equal(r.options.flush,true);assert.equal(r.options.tmpPath,r.file+'.tmp');}
  assert.equal(f.writes[1].options.compress,true);assert.equal(f.maxWrites,1);assert.equal(f.armed,undefined);assert.equal(f.jsonArmed,undefined);
});
test('disable completion and onDisabled observe disabled durable cache and DB',async()=>{
  const f=fixture(),a=f.addon();await f.states.flushAndroid();f.events=[];
  await f.setUserDisabled.call(a,true);
  assert.equal(a.active,false);assert.equal(a.bootstrap.started,false);assert.equal(f.diskAddon(a.id).userDisabled,true);assert.equal(f.diskState(a.id).enabled,false);
  const event=f.events.find(e=>e.name==='onDisabled');assert.ok(event);assert.equal(new Map(event.disk).get('/profile/addonStartup.json.lz4')['app-profile'].addons[a.id].enabled,false);
});
test('enable completion and onEnabled observe enabled durable state',async()=>{
  const f=fixture(),a=f.addon('test@example.org',false);await f.states.flushAndroid();await f.setUserDisabled.call(a,false);
  assert.equal(a.active,true);assert.equal(a.bootstrap.started,true);assert.equal(f.diskAddon(a.id).userDisabled,false);assert.equal(f.diskState(a.id).enabled,true);
  assert.ok(f.events.some(e=>e.name==='onEnabled'));
});
test('failure in either file rejects disable; same-value retry persists it',async()=>{
  for(const suffix of ['extensions.json','addonStartup.json.lz4']){
    const f=fixture(),a=f.addon();await f.states.flushAndroid();f.events=[];f.fail=r=>r.file.endsWith(suffix);
    await assert.rejects(f.setUserDisabled.call(a,true),/disk full/);assert.ok(!f.events.some(e=>e.name==='onDisabled'));
    f.fail=null;await f.setUserDisabled.call(a,true);assert.equal(f.diskAddon(a.id).userDisabled,true);assert.equal(f.diskState(a.id).enabled,false);assert.equal(f.db._saveError,null);
  }
});
test('a save does not resolve while the cache write is still pending',async()=>{
  const f=fixture();f.addon();const gate=deferred();f.writeGate=r=>r.file.endsWith('.lz4')?gate.promise:undefined;
  let done=false;const save=f.states.flushAndroid().then(()=>done=true);await tick();assert.equal(done,false);gate.resolve();await save;assert.equal(done,true);
});
test('mutations during a write drain again without concurrent temp-file writers',async()=>{
  const f=fixture(),a=f.addon();const gate=deferred();let first=true;f.writeGate=()=>{if(first){first=false;return gate.promise;}};
  const one=f.states.flushAndroid();await tick();a.userDisabled=true;a.active=false;f.db.updateXPIStates(a);f.db.saveChanges();const two=f.states.flushAndroid();gate.resolve();await Promise.all([one,two]);
  assert.equal(f.diskAddon(a.id).userDisabled,true);assert.equal(f.diskState(a.id).enabled,false);assert.equal(f.maxWrites,1);assert.ok(f.writes.length>=4);
});
test('concurrent disable-enable-disable operations are ordered and end disabled',async()=>{
  const f=fixture(),a=f.addon();await Promise.all([f.setUserDisabled.call(a,true),f.setUserDisabled.call(a,false),f.setUserDisabled.call(a,true)]);
  assert.deepEqual(f.operations,['disable:'+a.id,'enable:'+a.id,'disable:'+a.id]);assert.equal(a.active,false);assert.equal(a.bootstrap.started,false);assert.equal(f.diskState(a.id).enabled,false);
});
test('removal waits for durable absence and stops policy before notifying completion',async()=>{
  const f=fixture(),a=f.addon();await f.states.flushAndroid();await f.install.uninstallAddon(a,false);
  assert.equal(f.diskAddon(a.id),undefined);assert.equal(f.diskState(a.id),undefined);assert.equal(a.bootstrap.started,false);
  const event=f.events.find(e=>e.name==='onUninstalled');assert.ok(event);assert.equal(new Map(event.disk).get('/profile/extensions.json').addons.length,0);
});
test('queued enable after removal rejects stale handle instead of reviving it',async()=>{
  const f=fixture(),a=f.addon();const results=await Promise.allSettled([f.install.uninstallAddon(a,false),f.setUserDisabled.call(a,false)]);
  assert.equal(results[0].status,'fulfilled');assert.equal(results[1].status,'rejected');assert.match(results[1].reason.message,/no longer/);assert.equal(f.diskState(a.id),undefined);
});
test('pending removal and cancellation have durable cache state and notification',async()=>{
  const f=fixture(),a=f.addon();await f.install.uninstallAddon(a,true);assert.equal(f.diskAddon(a.id).pendingUninstall,true);assert.equal(f.diskState(a.id).enabled,false);assert.equal(a.bootstrap.started,false);
  await f.install.cancelUninstallAddon(a);assert.equal(f.diskAddon(a.id).pendingUninstall,false);assert.equal(f.diskState(a.id).enabled,true);assert.equal(a.bootstrap.started,true);assert.ok(f.events.some(e=>e.name==='onOperationCancelled'));
});
test('pending uninstall remains disabled when XPIState is resynchronized',async()=>{
  const f=fixture(),a=f.addon();a.pendingUninstall=true;f.db.updateXPIStates(a);await f.states.flushAndroid();assert.equal(f.diskState(a.id).enabled,false);
});
test('writer failure does not poison subsequent queued operations',async()=>{
  const f=fixture(),a=f.addon();f.fail=()=>true;await assert.rejects(f.setUserDisabled.call(a,true));f.fail=null;await f.setUserDisabled.call(a,false);assert.equal(f.diskState(a.id).enabled,true);
});
test('shutdown finalize drains the Android writer rather than DeferredTask',async()=>{
  const f=fixture();f.addon();await f.db.finalize();assert.equal(f.writes.length,2);assert.equal(f.deferred,undefined);
});
test('desktop retains DeferredTask and JSONFile without Android writes',async()=>{
  const f=fixture('linux');f.addon();f.db.saveChanges();f.states.save();await f.states.flushAndroid();assert.equal(f.deferred.delay,20);assert.equal(f.armed,true);assert.equal(f.jsonArmed,true);assert.equal(f.writes.length,0);
});
test('cold start always loads DB before scan and reconciliation before cache scheduling',async()=>{
  const f=fixture(),order=[];f.db.syncLoadDB=()=>order.push('db');f.states.scanForChanges=ignore=>{order.push('scan');assert.equal(ignore,false);return false;};
  f.context.XPIExports.XPIDatabaseReconcile={processFileChanges(){order.push('reconcile');return true;}};f.db.updateActiveAddons=()=>order.push('active');f.prefs.set('distro',false);f.prefs.set('schema',37);
  f.checkForChanges.call({processPendingFileChanges:()=>false},false);order.push('background');assert.deepEqual(order,['db','scan','db','reconcile','active','background']);
});
test('a failed Android startup reconciliation cannot fall through to backgrounds',async()=>{
  const f=fixture();f.db.syncLoadDB=()=>{};f.states.scanForChanges=()=>false;f.prefs.set('distro',false);f.context.XPIExports.XPIDatabaseReconcile={processFileChanges(){throw new Error('bad metadata');}};
  assert.throws(()=>f.checkForChanges.call({processPendingFileChanges:()=>false},false),/bad metadata/);
});
test('XPI synchronization repairs both enabled-cache/disabled-DB and the inverse',async()=>{
  for(const enabled of [false,true]){const f=fixture(),a=f.addon('test@example.org',enabled);const state=a.location.get(a.id);state.enabled=!enabled;f.db.updateXPIStates(a);assert.equal(state.enabled,enabled);assert.equal([...f.states.enabledAddons()].length,enabled?1:0);}
});
test('initial scan saves cannot replace a database which has not loaded',async()=>{
  const f=fixture();f.db.initialized=false;await f.states.flushAndroid();assert.equal(f.writes.length,0);f.db.initialized=true;f.addon();await f.states.flushAndroid();assert.equal(f.writes.length,2);
});

test('directory scan recovers a known first install missing from a non-sideload cache',async()=>{
  const f=fixture(),a=f.addon(),loc=a.location,state=loc.get(a.id);loc.delete(a.id);
  class File {constructor(id){this.path='/profile/extensions/'+id+'.xpi';}clone(){return this;}}
  f.context.Ci.nsIFile=File;f.context.XPIProvider={addTelemetry:()=>{}};
  f.states.initialStateData={'app-profile':{addons:{}}};f.prefs.set('build','build');
  Object.assign(loc,{enumerable:true,readAddons:()=>new Map([[a.id,new File(a.id)],['unknown@example.org',new File('unknown@example.org')]]),addFile(id,file){assert.equal(id,a.id);state.file=file;state.getModTime=()=>0;this.set(id,state);return state;}});
  assert.equal(f.states.scanForChanges(false),true);assert.equal(loc.has(a.id),true);assert.equal(loc.has('unknown@example.org'),false);
});
test('directory scan removes a cached identity when its actual file is gone',async()=>{
  const f=fixture(),a=f.addon(),loc=a.location;f.context.XPIProvider={addTelemetry:()=>{}};f.states.initialStateData={'app-profile':{addons:{}}};f.prefs.set('build','build');Object.assign(loc,{enumerable:true,readAddons:()=>new Map()});
  assert.equal(f.states.scanForChanges(false),true);assert.equal(loc.has(a.id),false);
});
test('new save requested from a just-completed writer is not lost',async()=>{
  const f=fixture(),a=f.addon();await f.states.flushAndroid();a.userDisabled=true;a.active=false;f.db.updateXPIStates(a);await f.states.flushAndroid();assert.equal(f.diskState(a.id).enabled,false);assert.equal(f.diskAddon(a.id).userDisabled,true);
});
test('AbortError from database IO rejects instead of falsely acknowledging completion',async()=>{
  const f=fixture();f.addon();f.context.IOUtils.writeJSON=async()=>{throw new DOMException('shutting down','AbortError');};await assert.rejects(f.states.flushAndroid(),{name:'AbortError'});
});
test('failed removal emits no completion event and its retained dirty state is retryable',async()=>{
  const f=fixture(),a=f.addon();await f.states.flushAndroid();f.events=[];f.fail=r=>r.file.endsWith('.lz4');await assert.rejects(f.install.uninstallAddon(a,false),/disk full/);assert.equal(f.events.some(e=>e.name==='onUninstalled'),false);assert.equal(a.bootstrap.started,false);f.fail=null;await f.states.flushAndroid();assert.equal(f.diskState(a.id),undefined);assert.equal(f.diskAddon(a.id),undefined);
});
test('invalid and system-disable operations preserve existing validation',async()=>{
  const f=fixture(),a=f.addon();a.location.isSystem=true;await assert.rejects(f.setUserDisabled.call(a,true),/Cannot disable system/);assert.equal(a.userDisabled,false);a.location.isSystem=false;a.location.locked=true;await assert.rejects(f.install.uninstallAddon(a,false),/locked install/);assert.equal(f.db.addonDB.has(a._key),true);
});

test('verified update keeps latest disabled state and persists new version before completion',async()=>{
  const f=fixture(),a=f.addon();const install=f.prepareInstall(a);await f.setUserDisabled.call(a,true);await install.startInstall();
  assert.ok(!f.events.some(e=>e.name==='onInstallFailed'));assert.equal(f.diskAddon(a.id).version,'2');assert.equal(f.diskState(a.id).version,'2');assert.equal(f.diskState(a.id).enabled,false);assert.equal(a.bootstrap.started,false);
  const event=f.events.find(e=>e.name==='onInstallEnded');assert.ok(event, String(f.errors.map(row=>row.at(-1)?.stack??row)));assert.equal(new Map(event.disk).get('/profile/addonStartup.json.lz4')['app-profile'].addons[a.id].version,'2');
});
test('update persistence failure reports onInstallFailed and never onInstallEnded',async()=>{
  const f=fixture(),a=f.addon();await f.states.flushAndroid();const install=f.prepareInstall(a);f.fail=r=>r.file.endsWith('.lz4');await install.startInstall();assert.ok(f.events.some(e=>e.name==='onInstallFailed'));assert.ok(!f.events.some(e=>e.name==='onInstallEnded'));f.fail=null;await f.states.flushAndroid();assert.equal(f.diskState(a.id).version,'2');
});
test('a queued update cannot resurrect an extension removed before it acquires the queue',async()=>{
  const f=fixture(),a=f.addon(),install=f.prepareInstall(a);await Promise.all([f.install.uninstallAddon(a,false),install.startInstall()]);assert.equal(f.diskState(a.id),undefined);assert.ok(f.events.some(e=>e.name==='onInstallCancelled'));assert.ok(!f.events.some(e=>e.name==='onInstallEnded'));
});
test('same-version reinstall can re-enable without a nested operation-queue deadlock',async()=>{
  const f=fixture(),a=f.addon('test@example.org',false),install=f.prepareInstall(a,'1');await install.startInstall();assert.equal(f.diskState(a.id).enabled,true);assert.ok(f.events.some(e=>e.name==='onInstallEnded'));
});

test('verified first install writes both stores before install completion',async()=>{
  const f=fixture(),old=f.addon(),state=old.location.get(old.id),install=f.prepareInstall(old,'1');install.existingAddon=null;f.db.addonDB.clear();old.location.clear();old.location.addAddon=function(addon){this.set(addon.id,state);state.syncWithDB(addon);};old.bootstrap.install=async()=>{};await install.startInstall();
  assert.equal(f.diskAddon(old.id).version,'1');assert.equal(f.diskState(old.id).enabled,true);assert.ok(f.events.some(e=>e.name==='onInstallEnded'));assert.ok(!f.events.some(e=>e.name==='onInstallFailed'), String(f.errors.map(row=>row.at(-1)?.stack??row)));
});
test('install listener cancellation changes neither store nor add-on choice',async()=>{
  const f=fixture(),a=f.addon();await f.states.flushAndroid();const before=clone([...f.files]),install=f.prepareInstall(a);install._callInstallListeners=()=>false;await install.startInstall();assert.deepEqual(clone([...f.files]),before);assert.equal(a.userDisabled,false);
});

test('enable while uninstall is pending records choice without restarting policy',async()=>{
  const f=fixture(),a=f.addon();await f.install.uninstallAddon(a,true);await f.setUserDisabled.call(a,true);await f.setUserDisabled.call(a,false);assert.equal(a.active,false);assert.equal(a.bootstrap.started,false);assert.equal(f.diskAddon(a.id).userDisabled,false);assert.equal(f.diskState(a.id).enabled,false);await f.install.cancelUninstallAddon(a);assert.equal(f.diskState(a.id).enabled,true);
});

(async()=>{let failed=0;for(const {name,run} of tests){let timer;try{await Promise.race([run(),new Promise((resolve,reject)=>{timer=setTimeout(()=>reject(new Error('test timed out; possible operation deadlock')),3000);})]);console.log('PASS '+name);}catch(error){failed++;console.error('FAIL '+name+'\n'+error.stack);}finally{clearTimeout(timer);}}console.log(`${tests.length-failed}/${tests.length} actual-source tests passed`);process.exitCode=failed?1:0;})();
