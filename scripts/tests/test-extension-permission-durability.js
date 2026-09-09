#!/usr/bin/env node
/* Execute production methods and the production per-ID scheduler. OS services
 * are controlled substitutes; this is not Gecko/Android runtime evidence. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = process.argv[2];
const EP = 'toolkit/components/extensions/ExtensionPermissions.sys.mjs';
const SCHEDULER = 'toolkit/components/extensions/ExtensionTaskScheduler.sys.mjs';
const GV = 'mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs';
const read = name => fs.readFileSync(path.join(source, name), 'utf8');
const plain = value => JSON.parse(JSON.stringify(value));
const perms = () => ({permissions: ['internal:privateBrowsingAllowed'], origins: [], data_collection: []});
const empty = () => ({permissions: [], origins: [], data_collection: []});
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const turn = () => new Promise(setImmediate);
const tests = [];
const test = (name, fn) => tests.push([name, fn]);

function environment({android=true, modern=false, disk={}, cache={}}={}) {
  const state = {blockers: new Set(), disk: plain(disk), writes: [], scheduled: 0, events: [], kv: new Map([['_version',1]]), cache: new Map(Object.entries(plain(cache)))};
  const cacheService = {
    async get(id, make) { if(!state.cache.has(id)) state.cache.set(id, await make()); return state.cache.get(id); },
    async set(id,p) {state.cache.set(id,p);}, async delete(id) {state.cache.delete(id);},
  };
  const kv = {async has(k) {return state.kv.has(k);}, async get(k,d) {return state.kv.has(k)?state.kv.get(k):d;},
    async put(k,v) {if(state.kvGate) await state.kvGate.promise; if(state.failKV) throw new Error('KV failed'); state.kv.set(k,v);},
    async delete(k) {if(state.kvGate) await state.kvGate.promise; state.kv.delete(k);}};
  const lazy = {
    JSONFile: class {constructor({path}) {this.path=path;} saveSoon() {state.scheduled++;} async finalize() {}},
    FileUtils:{getDir:()=>({path:'/profile/kv'})},
    KeyValueService:{RecoveryStrategy:{RENAME:1}, getOrCreateWithOptions:async()=>kv},
    StartupCache:{permissions:cacheService}, Management:{emit:(...args)=>state.events.push(args)},
  };
  class DefaultMap extends Map {constructor(make) {super();this.make=make;} get(k) {if(!this.has(k))this.set(k,this.make(k));return super.get(k);}}
  const context = vm.createContext({structuredClone,console,AppConstants:{platform:android?'android':'linux',NIGHTLY_BUILD:modern},
    XPCOMUtils:{declareLazy:()=>lazy},ExtensionUtils:{DefaultMap},
    PathUtils:{join:(...p)=>p.join('/')},Services:{dirsvc:{get:()=>({path:'/profile'})}},Ci:{nsIFile:{}},Cu:{reportError:()=>{}},
    DOMException:{isInstance:()=>false},WebExtensionPolicy:{getByID:()=>null},
    IOUtils:{profileBeforeChange:{addBlocker:(_name,fn)=>state.blockers.add(fn),removeBlocker:fn=>state.blockers.delete(fn)},readJSON:async()=>plain(state.disk),makeDirectory:async()=>{},
      async writeJSON(file,data,options) {
        const entry = {file,data:plain(data),options:plain(options)}; state.writes.push(entry);
        if(state.gate) await state.gate.promise;
        if(state.failWrite || state.failNextWrite) {state.failNextWrite=false;throw new Error('atomic write failed');}
        state.disk=plain(data);
      }}});
  vm.runInContext('Promise.withResolvers ??= function(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};',context);
  vm.runInContext(read(SCHEDULER).replace('export class ExtensionTaskScheduler','class ExtensionTaskScheduler'),context);
  let text = read(EP).split('export var OriginControls = {')[0];
  text = text.replace(/^import .*;\n/gm,'').replace('export var ExtensionPermissions','var ExtensionPermissions');
  vm.runInContext(text + '\nthis.api=ExtensionPermissions;', context, {filename:EP});
  return {state,api:context.api,context};
}

for(const operation of ['add','remove','removeAll']) {
  test(`${operation} completion waits for flushed atomic JSON`,async()=>{
    const initial = operation==='add'?{}:{a:perms()};
    const {api,state}=environment({disk:initial}); state.gate=deferred();
    let completed=false; const result=api[operation]('a',perms()).then(()=>{completed=true;});
    await turn(); assert.equal(completed,false); assert.equal(state.writes.length,1);
    assert.deepEqual(state.writes[0].options,{tmpPath:'/profile/extension-preferences.json.tmp',flush:true});
    assert.deepEqual(state.disk,initial); assert.equal(state.events.length,0);
    state.gate.resolve(); await result; assert.equal(state.scheduled,0);
    if(operation==='add') assert.deepEqual(state.disk.a,perms());
    else if(operation==='remove') assert.deepEqual(state.disk.a,empty());
    else assert.equal(state.disk.a,undefined);
  });
  test(`${operation} failure preserves committed memory and same-choice retry`,async()=>{
    const initial=operation==='add'?{}:{a:perms()};
    const {api,state}=environment({disk:initial,cache:initial}); state.failWrite=true;
    await assert.rejects(api[operation]('a',perms()),/atomic write failed/);
    assert.deepEqual(state.disk,initial); assert.deepEqual(plain(await api.get('a')),initial.a??empty());
    assert.equal(state.events.length,0); state.failWrite=false;
    await api[operation]('a',perms()); assert.equal(state.writes.length,2);
    if(operation==='add') assert.deepEqual(state.disk.a,perms());
    else if(operation==='remove') assert.deepEqual(state.disk.a,empty());
    else assert.equal(state.disk.a,undefined);
  });
}

test('different IDs serialize whole-file snapshots without lost grants',async()=>{
  const {api,state}=environment(); state.gate=deferred();
  const a=api.add('a',perms()), b=api.add('b',perms()); await turn();
  assert.equal(state.writes.length,1);state.gate.resolve();await Promise.all([a,b]);
  assert.deepEqual(state.disk,{a:perms(),b:perms()});assert.equal(state.writes.length,2);
});
test('a failed ID does not poison the next queued ID',async()=>{
  const {api,state}=environment(); state.gate=deferred();state.failNextWrite=true;
  const a=api.add('a',perms()); const handled=assert.rejects(a,/atomic write failed/);
  const b=api.add('b',perms());await turn();state.gate.resolve();await handled;await b;
  assert.deepEqual(state.disk,{b:perms()});
});
test('same-ID read and revoke remain behind a pending grant',async()=>{
  const {api,state}=environment();state.gate=deferred();
  const grant=api.add('a',perms());let readDone=false;
  const read=api.get('a').then(p=>{readDone=true;assert.deepEqual(plain(p),perms());});
  const revoke=api.remove('a',perms());await turn();assert.equal(readDone,false);
  state.gate.resolve();await Promise.all([grant,read,revoke]);assert.deepEqual(state.disk.a,empty());
});
test('graceful shutdown waits the complete cross-ID queue and test teardown detaches it',async()=>{
  const {api,state}=environment();state.gate=deferred();
  const a=api.add('a',perms()),b=api.add('b',perms());await turn();
  assert.equal(state.blockers.size,1);let complete=false;
  const shutdown=Promise.all([...state.blockers].map(fn=>fn())).then(()=>{complete=true;});
  await turn();assert.equal(complete,false);state.gate.resolve();await Promise.all([a,b,shutdown]);
  assert.deepEqual(state.disk,{a:perms(),b:perms()});
  await api._uninit({recreateStore:false});assert.equal(state.blockers.size,0);
});
test('callers cannot mutate a committed Android legacy record',async()=>{
  const {api,state}=environment({disk:{a:perms()}});const result=await api.get('a');result.permissions.length=0;
  assert.deepEqual(plain(await api.get('a')),perms());assert.deepEqual(state.disk.a,perms());
});
for(const modern of [false,true]) {
  test(`${modern?'KV':'JSON'} ignores stale derived grant and denial`,async()=>{
    const {api,state}=environment({modern,cache:{a:perms()}});
    assert.deepEqual(plain(await api.get('a')),empty());
    await api.add('a',perms());state.cache.set('a',empty());
    assert.deepEqual(plain(await api.get('a')),perms());
    assert.deepEqual(plain(state.cache.get('a')),perms());
    await api.removeAll('a');state.cache.set('a',perms());
    assert.deepEqual(plain(await api.get('a')),empty());
  });
}
test('modern KV still awaits its native write and emits no legacy JSON write',async()=>{
  const {api,state}=environment({modern:true});state.kvGate=deferred();let complete=false;
  const write=api.add('a',perms()).then(()=>{complete=true;});await turn();assert.equal(complete,false);
  state.kvGate.resolve();await write;assert.equal(state.writes.length,0);assert.equal(state.scheduled,0);
  assert.deepEqual(JSON.parse(state.kv.get('id-a')),perms());
});
test('modern KV write rejection stays visible and retryable',async()=>{
  const {api,state}=environment({modern:true});state.failKV=true;
  await assert.rejects(api.add('a',perms()),/KV failed/);state.failKV=false;
  await api.add('a',perms());assert.deepEqual(JSON.parse(state.kv.get('id-a')),perms());
});
test('desktop legacy scheduled persistence and cache behavior are preserved',async()=>{
  const {api,state}=environment({android:false});await api.add('a',perms());
  assert.equal(state.scheduled,1);assert.equal(state.writes.length,0);assert.deepEqual(state.disk,{});
  state.cache.set('a',empty());assert.deepEqual(plain(await api.get('a')),empty());
});

function bridge(uninstall) {
  const listeners=new Set();const Management={on:(event,fn)=>listeners.add(fn),off:(event,fn)=>listeners.delete(fn),
    emit:(id,tasks)=>{for(const fn of listeners)fn('cleanupAfterUninstall',id,tasks);}};
  const text=read(GV); const start=text.indexOf('  async uninstallWebExtension(aId) {');
  const end=text.indexOf('\n  async browserActionClick(',start);assert.ok(start>0&&end>start);
  const context=vm.createContext({lazy:{Management}});
  vm.runInContext('this.api={'+text.slice(start,end)+'};',context,{filename:GV});
  context.api.extensionById=async()=>({uninstall:()=>uninstall(Management)});
  return {api:context.api,listeners};
}
const task=(id,promise)=>({name:`Clear ExtensionPermissions for ${id}`,promise});
test('uninstall waits only the original exact-ID permission task',async()=>{
  const cleanup=deferred();const irrelevant=deferred();
  const {api,listeners}=bridge(m=>{m.emit('other',[task('other',irrelevant.promise)]);m.emit('a',[task('a',cleanup.promise),{name:'Clear storage',promise:irrelevant.promise}]);});
  let complete=false;const result=api.uninstallWebExtension('a').then(()=>{complete=true;});
  await turn();assert.equal(complete,false);cleanup.resolve();await result;assert.equal(listeners.size,0);
});
test('uninstall rejects original cleanup failure without silently retrying',async()=>{
  const cleanup=deferred();const release=deferred();let calls=0;
  const {api,listeners}=bridge(async m=>{calls++;m.emit('a',[task('a',cleanup.promise)]);await release.promise;});
  const result=api.uninstallWebExtension('a');const check=assert.rejects(result,/original failure/);
  await turn();cleanup.reject(new Error('original failure'));await turn();release.resolve();await check;
  assert.equal(calls,1);assert.equal(listeners.size,0);
});
for(const bad of ['missing','wrong-id','wrong-task','duplicate']) {
  test(`uninstall ${bad} cleanup cannot acknowledge success`,async()=>{
    const {api,listeners}=bridge(m=>{
      if(bad==='wrong-id')m.emit('b',[task('a',Promise.resolve())]);
      if(bad==='wrong-task')m.emit('a',[task('b',Promise.resolve())]);
      if(bad==='duplicate')m.emit('a',[task('a',Promise.resolve()),task('a',Promise.resolve())]);
    });
    await assert.rejects(api.uninstallWebExtension('a'),/Missing extension permission cleanup/);assert.equal(listeners.size,0);
  });
}
test('uninstall registry failure propagates and detaches observer',async()=>{
  const {api,listeners}=bridge(()=>{throw new Error('registry failure');});
  await assert.rejects(api.uninstallWebExtension('a'),/registry failure/);assert.equal(listeners.size,0);
});
test('pinned observer really emits the exact permission task before return',async()=>{
  const observer=read('toolkit/components/extensions/Extension.sys.mjs');
  assert.ok(observer.includes('`Clear ExtensionPermissions for ${addonId}`,\n      lazy.ExtensionPermissions.removeAll(addonId)'));
  assert.ok(observer.includes('Management.emit("cleanupAfterUninstall", addonId, tasks)'));
});
(async()=>{for(const [name,fn]of tests){await fn();console.log('PASS '+name);}console.log(`PASS ${tests.length} production-source tests; target runtime pending`);})().catch(e=>{console.error(e);process.exitCode=1;});
