/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = process.argv[2];
assert.ok(source, 'usage: node test-extension-update-controls.js PATCHED_SOURCE');
const text = fs.readFileSync(path.join(source, 'mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs'), 'utf8');
const start = text.indexOf('  getAutomaticUpdateSettings() {');
const end = text.indexOf('  validateBuiltInLocation(', start);
assert.ok(start > 0 && end > start);
const methods = text.slice(start, end);
const names = ['extensions.update.enabled', 'extensions.update.autoUpdateDefault'];
const tick = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const tests = [];
const test = (name,run) => tests.push({name,run});
function fixture() {
  const f = {users:new Map(), defaults:new Map(names.map(n=>[n,true])), locks:new Set(), writes:[], events:[], save:null, stale:true};
  const prefs = {
    getBoolPref(name, fallback) {return f.locks.has(name) ? f.defaults.get(name) : f.users.get(name) ?? f.defaults.get(name) ?? fallback;},
    prefIsLocked:name=>f.locks.has(name), prefHasUserValue:name=>f.users.has(name),
    setBoolPref(name,value) { assert.equal(typeof value,'boolean'); if(!f.locks.has(name))f.users.set(name,value); },
    clearUserPref:name=>f.users.delete(name),
    async savePrefFileAsync() { const request = {values:[...f.users]};f.writes.push(request);if(f.save)await f.save(request);f.disk=request.values; },
  };
  const manager = {
    get updateEnabled(){return prefs.getBoolPref(names[0],true);},
    shouldAutoUpdate:addon => addon.permission !== false && (addon.auto === 'on' || addon.auto !== 'off' && prefs.getBoolPref(names[1],true)),
    UPDATE_WHEN_PERIODIC_UPDATE:16, UPDATE_WHEN_USER_REQUESTED:1,
    updatePromptHandler:()=>{f.events.push('prompt');},
  };
  const repository = {isMetadataStale:()=>{f.events.push('stale');return f.stale;},async backgroundUpdateCheck(){f.events.push('metadata');if(f.metadata)await f.metadata;}};
  const context=vm.createContext({Services:{prefs},lazy:{AddonManager:manager,AddonRepository:repository},ExtensionInstallListener:class {constructor(resolve){this.resolve=resolve;}},console});
  f.controller=vm.runInContext('({' + methods + '})',context);
  f.addon={findUpdates(listener,reason){f.events.push(['manifest',reason]);if(f.manifest){f.manifest(listener);return;}listener.onUpdateAvailable(f.addon,f.install);}};
  f.install={addListener(listener){f.listener=listener;},install(){f.events.push('install');f.listener.resolve({extension:{id:'updated'}});}};
  f.controller.extensionById=async()=>{f.events.push('lookup');if(f.lookup)await f.lookup;return f.addon;};
  f.prefs=prefs;
  return f;
}
test('fresh defaults, mixed values and lock state are effective, read-only facts',async()=>{
  const f=fixture();assert.equal(f.controller.getAutomaticUpdateSettings().enabled,true);
  f.users.set(names[1],false);assert.equal(f.controller.getAutomaticUpdateSettings().enabled,false);
  f.locks.add(names[1]);const state=f.controller.getAutomaticUpdateSettings();assert.equal(state.locked,true);assert.equal(state.enabled,true);
  assert.equal(f.writes.length,0);
});
test('nonboolean and locked requests do not partially write',async()=>{
  const f=fixture();await assert.rejects(f.controller.setAutomaticUpdateSettings('false'),/boolean/);
  f.locks.add(names[1]);await assert.rejects(f.controller.setAutomaticUpdateSettings(false),/locked/);
  assert.equal(f.users.size,0);assert.equal(f.writes.length,0);assert.equal(f.controller._pendingAutomaticUpdateSettings,0);
});
test('unusable profile or disk fails preflight before user-pref mutation',async()=>{
  const f=fixture();f.save=()=>{throw Error('no profile');};await assert.rejects(f.controller.setAutomaticUpdateSettings(false),/no profile/);
  assert.equal(f.users.size,0);assert.equal(f.writes.length,1);
});
test('queued choice closes automatic admission until actual write completes',async()=>{
  const f=fixture();const gate=deferred();f.save=()=>gate.promise;
  let complete=false;const change=f.controller.setAutomaticUpdateSettings(false).then(state=>{complete=true;return state;});
  assert.equal(await f.controller.updateWebExtension('test',true),null);assert.deepEqual(f.events,[]);
  await tick();assert.equal(complete,false);assert.equal(f.users.size,0);
  gate.resolve();assert.equal((await change).enabled,false);assert.deepEqual(f.disk,names.map(n=>[n,false]));
});
test('policy lock acquired during preflight rejects before mutation',async()=>{
  const f=fixture();const gate=deferred();f.save=()=>gate.promise;const change=f.controller.setAutomaticUpdateSettings(false);
  await tick();f.locks.add(names[0]);gate.resolve();await assert.rejects(change,/locked/);assert.equal(f.users.size,0);
});
test('failed final write retains native state without claiming disk success and queue can retry',async()=>{
  const f=fixture();let n=0;f.save=()=>{if(++n===2)throw Error('disk full');};
  await assert.rejects(f.controller.setAutomaticUpdateSettings(false),/disk full/);assert.deepEqual([...f.users],names.map(n=>[n,false]));
  f.save=null;assert.equal((await f.controller.setAutomaticUpdateSettings(false)).enabled,false);
});
test('unconfirmed On cannot reopen automatic admission through an unrelated read',async()=>{
  const f=fixture();f.users.set(names[0],false);f.users.set(names[1],false);let n=0;
  f.save=()=>{if(++n===2)throw Error('disk full');};
  await assert.rejects(f.controller.setAutomaticUpdateSettings(true),/disk full/);
  const state=f.controller.getAutomaticUpdateSettings();assert.equal(state.enabled,true);assert.equal(state.saveConfirmed,false);
  assert.equal(await f.controller.updateWebExtension('test',true),null);assert.deepEqual(f.events,[]);
  f.controller.getAutomaticUpdateSettings();assert.equal(f.controller.automaticUpdatesAllowed(),false);
  f.save=null;assert.equal((await f.controller.setAutomaticUpdateSettings(true)).saveConfirmed,true);
  assert.equal((await f.controller.updateWebExtension('test',true)).extension.id,'updated');
});
test('failed write preserves external newer values',async()=>{
  const f=fixture();f.users.set(names[0],false);f.users.set(names[1],true);let n=0;
  f.save=()=>{if(++n===2){f.users.set(names[0],false);throw Error('disk full');}};
  await assert.rejects(f.controller.setAutomaticUpdateSettings(true),/disk full/);
  assert.equal(f.users.get(names[0]),false);assert.equal(f.users.get(names[1]),true);
});
test('same-value external writer is never erased by inferred rollback after failure',async()=>{
  const f=fixture();const gate=deferred();let n=0;f.save=()=>{if(++n===2)return gate.promise;};
  const change=f.controller.setAutomaticUpdateSettings(false);await tick();
  // A distinct writer deliberately chooses the same native value while the
  // persistence request is outstanding. Value equality cannot identify ownership.
  for(const name of names)f.prefs.setBoolPref(name,false);
  gate.reject(Error('disk full'));await assert.rejects(change,/disk full/);
  assert.deepEqual([...f.users],names.map(name=>[name,false]));
  assert.equal(f.controller.getAutomaticUpdateSettings().enabled,false);
});
test('concurrent choices serialize with snapshots and each gets its own state',async()=>{
  const f=fixture();const gate=deferred();let n=0;f.save=()=>{if(++n===2)return gate.promise;};
  const off=f.controller.setAutomaticUpdateSettings(false),on=f.controller.setAutomaticUpdateSettings(true);
  await tick();assert.equal(f.writes.length,2);assert.equal(f.controller.automaticUpdatesAllowed(),false);
  gate.resolve();assert.equal((await off).enabled,false);assert.equal((await on).enabled,true);
  assert.deepEqual(f.disk,names.map(n=>[n,true]));assert.equal(f.controller._pendingAutomaticUpdateSettings,0);
});
test('automatic off stops before metadata lookup and manifest',async()=>{
  const f=fixture();f.users.set(names[0],false);assert.equal(await f.controller.updateWebExtension('test',true),null);assert.deepEqual(f.events,[]);
});
test('off while metadata is in flight prevents subsequent lookup and manifest',async()=>{
  const f=fixture();const gate=deferred();f.metadata=gate.promise;const update=f.controller.updateWebExtension('test',true);
  await f.controller.setAutomaticUpdateSettings(false);gate.resolve();assert.equal(await update,null);assert.deepEqual(f.events,['stale','metadata']);
});
test('off while extension lookup is in flight prevents manifest',async()=>{
  const f=fixture();f.stale=false;const gate=deferred();f.lookup=gate.promise;const update=f.controller.updateWebExtension('test',true);
  await tick();await f.controller.setAutomaticUpdateSettings(false);gate.resolve();assert.equal(await update,null);assert.deepEqual(f.events,['stale','lookup']);
});
test('off or per-addon policy at final admission prevents XPI installation',async()=>{
  for(const mode of ['global-off','per-addon-off','permission-denied','default-off']){
    const f=fixture();let listener;f.manifest=x=>{listener=x;};const update=f.controller.updateWebExtension('test',true);await tick();
    if(mode==='global-off')await f.controller.setAutomaticUpdateSettings(false);
    if(mode==='per-addon-off')f.addon.auto='off';if(mode==='permission-denied')f.addon.permission=false;if(mode==='default-off')f.users.set(names[1],false);
    listener.onUpdateAvailable(f.addon,f.install);assert.equal(await update,null);assert.equal(f.events.includes('install'),false,mode);
  }
});
test('automatic enabled installs with periodic reason and retains signed prompt handler',async()=>{
  const f=fixture();const result=await f.controller.updateWebExtension('test',true);assert.equal(result.extension.id,'updated');
  assert.ok(f.events.some(x=>Array.isArray(x)&&x[1]===16));assert.equal(typeof f.install.promptHandler,'function');f.install.promptHandler({});assert.ok(f.events.includes('prompt'));
});
test('per-addon explicit enable retains desktop mixed-default behavior',async()=>{
  const f=fixture();f.users.set(names[1],false);f.addon.auto='on';assert.equal(f.controller.getAutomaticUpdateSettings().enabled,false);
  assert.equal((await f.controller.updateWebExtension('test',true)).extension.id,'updated');
});
test('manual update remains admitted while automatic off and uses user-request reason',async()=>{
  const f=fixture();f.users.set(names[0],false);f.users.set(names[1],false);f.addon.auto='off';
  assert.equal((await f.controller.updateWebExtension('test',false)).extension.id,'updated');assert.ok(f.events.some(x=>Array.isArray(x)&&x[1]===1));
});
test('an already started install may finish after automatic setting changes',async()=>{
  const f=fixture();f.install.install=()=>{f.events.push('install');};const update=f.controller.updateWebExtension('test',true);await tick();assert.ok(f.events.includes('install'));
  await f.controller.setAutomaticUpdateSettings(false);f.listener.resolve({extension:{id:'finished'}});assert.equal((await update).extension.id,'finished');
});
(async()=>{for(const {name,run} of tests){await run();console.log('PASS '+name);}console.log(`PASS ${tests.length} actual-source JavaScript control tests (native I/O and Android runtime not executed)`);})().catch(error=>{console.error(error);process.exitCode=1;});
