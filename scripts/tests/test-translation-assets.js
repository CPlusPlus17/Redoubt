/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto, randomUUID } = require('node:crypto');
const { Duplex } = require('node:stream');
const { createZstdDecompress } = require('node:zlib');
const root = path.resolve(__dirname, '../..');
const sourceRoot = process.argv[2];
assert.ok(sourceRoot, 'usage: node test-translation-assets.js PATCHED_SOURCE');
const moduleSource = fs.readFileSync(path.join(sourceRoot, 'toolkit/components/translations/AndroidTranslationAssets.sys.mjs'), 'utf8');
const catalogBytes = fs.readFileSync(path.join(root, 'assets/translations/catalog.json'));
const catalog = JSON.parse(catalogBytes);
const wasm = fs.readFileSync(path.join(root, 'assets/translations/bergamot-translator.wasm.zst'));
const evidence = path.join(root, 'docs/android/evidence/lw-m7-16');
const model = JSON.parse(fs.readFileSync(path.join(evidence, 'model-fixture.json'))).record;
const modelBytes = fs.readFileSync(path.join(evidence, 'vocab.vien.spm.zst'));
const clone = x => JSON.parse(JSON.stringify(x));
const deferred = () => { let resolve; const promise = new Promise(r => {resolve=r;}); return {promise,resolve}; };
const tick = () => new Promise(r => setImmediate(r));
function response(bytes, url) {
  const r = new Response(bytes);
  Object.defineProperty(r, 'url', {value:url});
  return r;
}
function fixture({channel='release', network, catalogData=catalogBytes}={}) {
  const state = {files:new Map(),fetches:[],timers:new Map(),observers:new Map(),writes:[],moves:[],deletions:[],writeGate:null,moveGate:null,movesStarted:[]};
  const IOUtils = {
    async read(file, options={}) { if(!state.files.has(file)) throw new Error('NotFoundError'); return new Uint8Array(state.files.get(file).slice(0,options.maxBytes)); },
    async makeDirectory() {},
    async write(file, bytes) { state.writes.push(file); if(state.writeGate) await state.writeGate.promise; state.files.set(file,new Uint8Array(bytes)); },
    async move(from,to) { state.movesStarted.push(to);if(state.moveGate)await state.moveGate.promise;assert.ok(state.files.has(from)); state.files.set(to,state.files.get(from)); state.files.delete(from); state.moves.push(to); },
    async remove(file, options={}) { state.deletions.push(file); for(const name of state.files.keys()) if(name===file || (options.recursive && name.startsWith(file+'/'))) state.files.delete(name); },
  };
  let timerId=0;
  const context = vm.createContext({
    crypto:webcrypto, URL, Intl, Blob, Response, TextDecoder, Uint8Array, ArrayBuffer, DOMException,
    AbortController, structuredClone, console, IOUtils,
    PathUtils:{profileDir:'/profile',join:path.posix.join,parent:path.posix.dirname},
    DecompressionStream:class { constructor(format) { assert.equal(format,'zstd'); return Duplex.toWeb(createZstdDecompress()); } },
    Services:{obs:{addObserver(fn,topic){state.observers.set(topic,fn);}},uuid:{generateUUID:()=>({toString:()=>'{'+randomUUID()+'}'})}},
    ChromeUtils:{defineESModuleGetters(target) { Object.assign(target, {
      AppConstants:{platform:'android',MOZ_UPDATE_CHANNEL:channel},
      setTimeout(fn,ms){const id=++timerId;state.timers.set(id,{fn,ms});return id;},
      clearTimeout(id){state.timers.delete(id);},
    });}},
    async fetch(url,options) {
      state.fetches.push({url,options});
      if(url.endsWith('/catalog.json')) return response(catalogData,url);
      if(url.startsWith('chrome:') && url.endsWith('/bergamot-translator.wasm.zst')) return response(wasm,url);
      if(network) return network(url,options,state);
      assert.equal(url,'https://firefox-settings-attachments.cdn.mozilla.net/'+model.attachment.location);
      return response(modelBytes,url);
    },
  });
  vm.runInContext(moduleSource.replaceAll('export async function ', 'async function ').replaceAll('export class ','class ')+'\nglobalThis.exports={AndroidTranslationAssets,decompressAndroidTranslationAsset,validateRecord,isEligible};',context);
  return {state,context,...context.exports,provider:new context.exports.AndroidTranslationAssets()};
}
const tests=[];
function test(name,fn) {tests.push({name,fn});}
function networkRows(f) {return f.state.fetches.filter(r=>r.url.startsWith('https:'));}
async function download(f,records=[model],signal) {return f.provider.withDownloadOperation(op=>f.provider.downloadRecords(records,op),signal);}
const modelPath='/profile/redoubt-translations-v1/'+model.attachment.hash+'.zst';

test('complete pinned catalog preserves exact Android and release targeting without network',async()=>{
  const f=fixture();const rows=await f.provider.client('models').get();
  assert.equal(rows.length,347);assert.equal((await f.provider.client('wasm').get()).length,1);
  assert.ok(rows.some(r=>r.filter_expression==="env.appinfo.OS == 'Android'"));
  assert.ok(!rows.some(r=>r.filter_expression==="env.appinfo.OS != 'Android'"));
  assert.ok(!rows.some(r=>r.filter_expression.includes('env.channel')));
  assert.equal(networkRows(f).length,0);
});
test('nightly eligibility preserves the exact reviewed targeted records',async()=>{
  const f=fixture({channel:'nightly'});assert.equal((await f.provider.client('models').get()).length,362);
  assert.equal(networkRows(f).length,0);
});
test('metadata filters and returned-record mutations cannot change the catalog',async()=>{
  const f=fixture();const rows=await f.provider.client('models').get({filters:{sourceLanguage:'vi'}});
  assert.ok(rows.length>0 && rows.every(r=>r.sourceLanguage==='vi'));rows[0].attachment.location='evil';
  assert.ok(!(await f.provider.client('models').get()).some(r=>r.attachment.location==='evil'));
});
test('missing and same-size corrupted catalogs fail before network',async()=>{
  for(const bytes of [Buffer.alloc(0),Buffer.concat([Buffer.from('!'),catalogBytes.subarray(1)])]) {
    const f=fixture({catalogData:bytes});await assert.rejects(f.provider.client('models').get());assert.equal(networkRows(f).length,0);
  }
});
test('passive cache and status calls never download missing models',async()=>{
  const f=fixture();await assert.rejects(f.provider.client('models').attachments.download(model));
  assert.equal(await f.provider.client('models').attachments.isDownloaded(model),false);
  await assert.rejects(f.provider.client('models').sync());assert.equal(networkRows(f).length,0);
});
test('bundled WASM passes real compressed and decompressed integrity without network',async()=>{
  const f=fixture();const result=await f.provider.read(catalog.wasm[0]);assert.equal(result.buffer.byteLength,wasm.length);
  assert.equal(networkRows(f).length,0);
});
test('explicit operation downloads one exact asset with no credentials/referrer/redirect/discovery',async()=>{
  const f=fixture();await download(f);assert.deepEqual(Buffer.from(f.state.files.get(modelPath)),modelBytes);
  const [request]=networkRows(f);assert.equal(networkRows(f).length,1);
  assert.equal(request.options.credentials,'omit');assert.equal(request.options.referrerPolicy,'no-referrer');
  assert.equal(request.options.redirect,'error');assert.equal(request.options.cache,'no-store');
  assert.equal(f.state.files.size,1);assert.equal(f.state.timers.size,0);
});
test('offline cache survives a new provider and status/deletion reflect real files',async()=>{
  const f=fixture();await download(f);const restarted=new f.AndroidTranslationAssets();
  assert.equal(await restarted.client('models').attachments.isDownloaded(model),true);
  await restarted.client('models').attachments.download(model);assert.equal(networkRows(f).length,1);
  await restarted.delete(model);assert.equal(await restarted.client('models').attachments.isDownloaded(model),false);
  assert.equal(networkRows(f).length,1);
});
test('unlisted IDs, changed URLs and changed decompression pins cannot authorize transfer',async()=>{
  for(const mutate of [r=>r.id=randomUUID(),r=>r.attachment.location='../evil.zst',r=>r.decompressedHash='0'.repeat(64)]) {
    const f=fixture();const altered=clone(model);mutate(altered);await assert.rejects(download(f,[altered]));assert.equal(networkRows(f).length,0);
  }
});
test('record validator rejects URL tricks, unknown targeting and excessive size',async()=>{
  const f=fixture();
  for(const mutate of [r=>r.attachment.location='//example.org/evil.zst',r=>r.attachment.location+='?next=x',r=>r.filter_expression='true',r=>r.attachment.size=2**30,r=>r.decompressedSize=2**30]) {
    const altered=clone(model);mutate(altered);assert.throws(()=>f.validateRecord(altered,'models'));
  }
});
for(const kind of ['truncated','same-size corruption','oversized','redirect','unexpected URL','length mismatch']) {
  test(kind+' response leaves no usable cache or temporary file',async()=>{
    const f=fixture({network:(url)=>{
      let bytes=modelBytes;
      if(kind==='truncated')bytes=bytes.subarray(0,-1);
      if(kind==='same-size corruption')bytes=Buffer.concat([Buffer.from('!'),bytes.subarray(1)]);
      if(kind==='oversized')bytes=Buffer.concat([bytes,Buffer.from('!')]);
      const r=response(bytes,kind==='unexpected URL'?'https://evil.invalid/':url);
      if(kind==='redirect')Object.defineProperty(r,'redirected',{value:true});
      if(kind==='length mismatch')r.headers.set('content-length','1');
      return r;
    }});
    await assert.rejects(download(f));assert.equal(f.state.files.size,0);assert.equal(f.state.timers.size,0);
  });
}
test('inference decompression uses real zstd, exact expanded size and expanded hash',async()=>{
  const f=fixture();const output=await f.decompressAndroidTranslationAsset(new Blob([modelBytes]),model);assert.equal(output.byteLength,model.decompressedSize);
  for(const altered of [{...model,decompressedSize:1},{...model,decompressedHash:'0'.repeat(64)}]) {
    await assert.rejects(f.decompressAndroidTranslationAsset(new Blob([modelBytes]),altered));
  }
});
test('cancelled operation rejects promptly and late response cannot cache',async()=>{
  const gate=deferred();const requested=deferred();const f=fixture({network:async(url)=>{requested.resolve();await gate.promise;return response(modelBytes,url);}});
  const controller=new AbortController();const result=download(f,[model],controller.signal);await requested.promise;controller.abort();
  await assert.rejects(result,{name:'AbortError'});gate.resolve();await tick();await tick();assert.equal(f.state.files.size,0);
});
test('transfer timeout aborts the operation and leaves no cache',async()=>{
  const gate=deferred();const requested=deferred();const f=fixture({network:async(url)=>{requested.resolve();await gate.promise;return response(modelBytes,url);}});
  const result=download(f);await requested.promise;const timer=[...f.state.timers.values()].find(t=>t.ms===60000);assert.ok(timer);timer.fn();
  await assert.rejects(result,{name:'AbortError'});gate.resolve();await tick();assert.equal(f.state.files.size,0);
});
test('Delete All cancels in-flight transfer and cannot be undone by late completion',async()=>{
  const gate=deferred();const requested=deferred();const f=fixture({network:async(url)=>{requested.resolve();await gate.promise;return response(modelBytes,url);}});
  const result=download(f);result.catch(()=>{});await requested.promise;const deleted=await f.provider.deleteAll();assert.equal(deleted.length,377);
  await assert.rejects(result);gate.resolve();await tick();await tick();assert.equal(f.state.files.size,0);
});
test('deletion serializes with an already-writing cache commit and cleans its temporary file',async()=>{
  const f=fixture();f.state.writeGate=deferred();const result=download(f);result.catch(()=>{});
  while(!f.state.writes.length)await tick();const deletion=f.provider.delete(model);await tick();f.state.writeGate.resolve();
  await deletion;await assert.rejects(result);assert.equal(f.state.files.size,0);
});
test('concurrent operations preserve cancellation identity and one valid atomic cache',async()=>{
  const gate=deferred();let started=0;const requested=deferred();const f=fixture({network:async(url)=>{started++;if(started===1){requested.resolve();await gate.promise;}return response(modelBytes,url);}});
  const controller=new AbortController();const first=download(f,[model],controller.signal);first.catch(()=>{});await requested.promise;
  const second=download(f);controller.abort();await assert.rejects(first);gate.resolve();await second;
  assert.deepEqual(Buffer.from(f.state.files.get(modelPath)),modelBytes);assert.equal(f.state.files.size,1);
});
test('Delete All also cancels operations still selecting metadata',async()=>{
  const f=fixture();const gate=deferred();const selected=deferred();const result=f.provider.withDownloadOperation(async op=>{selected.resolve();await gate.promise;return f.provider.downloadRecords([model],op);});result.catch(()=>{});
  await selected.promise;await f.provider.deleteAll();await assert.rejects(result);gate.resolve();await tick();assert.equal(networkRows(f).length,0);
});
test('operation cannot reuse authorization after success or target a second record set',async()=>{
  const f=fixture();let old;await f.provider.withDownloadOperation(async op=>{old=op;await f.provider.downloadRecords([model],op);await assert.rejects(f.provider.downloadRecords([model],op));});
  await assert.rejects(f.provider.downloadRecords([model],old));assert.equal(networkRows(f).length,1);
});
test('shutdown aborts active transfers and refuses new authorizations',async()=>{
  const f=fixture();f.state.observers.get('quit-application')();await assert.rejects(download(f),{name:'AbortError'});assert.equal(networkRows(f).length,0);
});

function sourceModule(context, relative, result) {
  const source=fs.readFileSync(path.join(sourceRoot,relative),'utf8')
    .replace(/^import\s[\s\S]*?;\n/gm,'').replaceAll('export class ','class ').replaceAll('export const ','const ');
  return vm.runInContext('(()=>{\n'+source+'\nreturn '+result+';})()',context,{filename:relative});
}
function parentFixture() {
  const f=fixture();const context=f.context;
  const modules={AndroidTranslationAssets:{instance:f.provider},setTimeout,TranslationsFeature:{isEnabled:true}};
  context.AppConstants={platform:'android',MOZ_UPDATE_CHANNEL:'release',DEBUG:false,ENABLE_WEBDRIVER:false};
  context.JSWindowActorParent=class {};
  context.Ci={nsIBrowserHandler:{}};
  context.console={createInstance:()=>({log(){},warn(){},error(){},debug(){}})};
  context.Services.prefs={addObserver(){},removeObserver(){},getBoolPref:(_,fallback)=>fallback};
  context.Services.obs.removeObserver=()=>{};
  context.Services.obs.notifyObservers=()=>{};
  context.Services.locale={appLocaleAsBCP47:'en-US'};
  const version=v=>{const m=/^(\d+)\.(\d+)(?:a(\d*))?$/.exec(v);return [Number(m[1]),Number(m[2]),m[3]===undefined?1:0,Number(m[3]||0)];};
  context.Services.vc={compare(a,b){const aa=version(a),bb=version(b);for(let i=0;i<aa.length;i++){if(aa[i]!==bb[i])return aa[i]>bb[i]?1:-1;}return 0;}};
  context.ChromeUtils.defineLazyGetter=(target,name,getter)=>Object.defineProperty(target,name,{configurable:true,get(){const value=getter();Object.defineProperty(target,name,{value,configurable:true});return value;}});
  context.ChromeUtils.defineESModuleGetters=(target,mapping)=>{for(const key of Object.keys(mapping)){Object.defineProperty(target,key,{configurable:true,get(){if(!(key in modules))throw new Error('Unexpected module '+key);return modules[key];}});}};
  context.ChromeUtils.importESModule=url=>url.includes('AppConstants')?{AppConstants:context.AppConstants}:{AndroidTranslationAssets:{instance:f.provider}};
  context.ChromeUtils.now=()=>0;
  context.ChromeUtils.addProfilerMarker=()=>{};
  context.XPCOMUtils={defineLazyServiceGetters(){},defineLazyPreferenceGetter(target,key,pref,defaultValue,update,transform){target[key]=transform?transform(defaultValue):defaultValue;}};
  const utils=sourceModule(context,'toolkit/components/translations/TranslationsUtils.mjs','TranslationsUtils');modules.TranslationsUtils=utils;
  const Parent=sourceModule(context,'toolkit/components/translations/actors/TranslationsParent.sys.mjs','TranslationsParent');
  const actor=new Parent();actor.manager={};actor.browsingContext={currentWindowGlobal:actor.manager};actor.innerWindowId=12;
  let translates=0;actor.translate=async()=>{translates++;};
  return {...f,Parent,actor,modules,utils,translated:()=>translates};
}

test('actual Parent selection retains complete direct and pivot record sets without RS clients',async()=>{
  const f=parentFixture();let records;f.provider.downloadRecords=async selected=>{records=selected;};
  await f.actor.translateFromUser({sourceLanguage:'es',targetLanguage:'en'},true);
  assert.ok(records.length>=2 && records.every(r=>r.sourceLanguage==='es' && r.targetLanguage==='en'));
  assert.ok(records.some(r=>r.fileType==='model'));assert.ok(records.some(r=>r.fileType==='vocab'));
  await f.actor.translateFromUser({sourceLanguage:'es',targetLanguage:'fr'},true);
  const pairs=new Set(records.map(r=>r.sourceLanguage+'-'+r.targetLanguage));assert.deepEqual([...pairs].sort(),['en-fr','es-en']);
  assert.equal(f.translated(),2);assert.equal(networkRows(f).length,0);
});
test('actual Parent size, passive engine payload and false-download request cannot authorize transfers',async()=>{
  const f=parentFixture();const size=await f.Parent.getExpectedTranslationDownloadSize('es','en');assert.ok(size>0);
  await assert.rejects(f.Parent.getTranslationsEnginePayload({sourceLanguage:'es',targetLanguage:'en'}));
  await assert.rejects(f.actor.translateFromUser({sourceLanguage:'es',targetLanguage:'en'},false),/MODEL_DOWNLOAD_REQUIRED/);
  assert.equal(f.translated(),0);assert.equal(networkRows(f).length,0);
});
test('actual Parent refuses stale documents before operation selection',async()=>{
  const f=parentFixture();f.actor.browsingContext.currentWindowGlobal={};
  await assert.rejects(f.actor.translateFromUser({sourceLanguage:'es',targetLanguage:'en'},true),{name:'AbortError'});
  assert.equal(f.state.fetches.length,0);assert.equal(f.translated(),0);
});
test('actual Parent pagehide cancellation prevents late preparation from translating',async()=>{
  const f=parentFixture();const gate=deferred(),requested=deferred();const read=f.provider.read.bind(f.provider);
  f.provider.read=async record=>{requested.resolve();await gate.promise;return read(record);};
  const pending=f.actor.translateFromUser({sourceLanguage:'es',targetLanguage:'en'},true);pending.catch(()=>{});await requested.promise;
  await f.actor.receiveMessage({name:'Translations:PageHidden',data:{}});
  await assert.rejects(pending,{name:'AbortError'});gate.resolve();await tick();assert.equal(f.translated(),0);assert.equal(networkRows(f).length,0);
});
test('actual Parent rechecks current WindowGlobal after asynchronous engine preparation',async()=>{
  const f=parentFixture();const read=f.provider.read.bind(f.provider);
  f.provider.read=async record=>{const result=await read(record);f.actor.browsingContext.currentWindowGlobal={};return result;};
  await assert.rejects(f.actor.translateFromUser({sourceLanguage:'es',targetLanguage:'en'},true),{name:'AbortError'});
  assert.equal(f.translated(),0);assert.equal(networkRows(f).length,0);
});
test('actual language download and Delete All use the new provider without a Remote Settings constructor',async()=>{
  const f=parentFixture();let selected;f.provider.downloadRecords=async rows=>{selected=rows;};
  await f.Parent.downloadLanguageFiles('es');assert.ok(selected.some(r=>r.sourceLanguage==='es'));assert.ok(selected.some(r=>r.targetLanguage==='es'));
  await f.Parent.downloadAllFiles();assert.ok(selected.length>200);
  const groups=new Map();for(const record of selected){const key=record.sourceLanguage+'-'+record.targetLanguage;const types=groups.get(key)||new Set();types.add(record.fileType);groups.set(key,types);}
  for(const types of groups.values()){assert.ok(types.has('model'));assert.ok(types.has('vocab')||(types.has('srcvocab')&&types.has('trgvocab')));}
  console.log('CATALOG_INVENTORY '+JSON.stringify({selectedRecords:selected.length,completeDirectionalPairs:groups.size,sourceLanguages:new Set(selected.map(r=>r.sourceLanguage)).size,targetLanguages:new Set(selected.map(r=>r.targetLanguage)).size}));
  const removed=await f.utils.deleteAllLanguageFiles();assert.equal(removed.length,377);assert.equal(networkRows(f).length,0);
});

function bridgeFixture() {
  const context=vm.createContext({console,Promise,AbortController,DOMException});
  const state={translations:[],downloads:[],metadata:0};
  const Parent={
    downloadAllFiles:signal=>{state.downloads.push({type:'all',signal});return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('cancelled'))));},
    downloadLanguageFiles:(language,signal)=>{state.downloads.push({language,signal});return Promise.resolve();},
    getSupportedLanguages:async()=>{state.metadata++;return {languagePairs:[]};},
  };
  const actor={translateFromUser(pair,allow,signal){state.translations.push({pair,allow,signal});return new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('cancelled'))));}};
  context.GeckoViewModule=class {getActor(){return actor;}static initLogging(){return {debug(){},warn(){}};}};
  context.ChromeUtils={defineESModuleGetters(target){Object.assign(target,{TranslationsParent:Parent,TranslationsUtils:{isLangTagValid:x=>typeof x==='string'&&/^[a-z]{2}$/.test(x)}});}};
  context.Cu={isInAutomation:false};context.Services={prefs:{getBoolPref:()=>false}};
  const result=sourceModule(context,'mobile/shared/modules/geckoview/GeckoViewTranslations.sys.mjs','({GeckoViewTranslations,GeckoViewTranslationsSettings})');
  const bridge=new result.GeckoViewTranslations();bridge.window={removeEventListener(){}};
  return {state,bridge,settings:result.GeckoViewTranslationsSettings};
}
function event(target,name,data) {return new Promise((resolve,reject)=>target.onEvent(name,data,{onSuccess:resolve,onError:error=>reject(new Error(String(error)))}));}
test('actual native bridge defaults missing network flag to false and scopes cancellation by UUID',async()=>{
  const f=bridgeFixture();const id=randomUUID();const pending=event(f.bridge,'GeckoView:Translations:Translate',{requestId:id,sourceLanguage:'es',targetLanguage:'en'});pending.catch(()=>{});await tick();
  assert.equal(f.state.translations[0].allow,false);
  assert.equal(await event(f.bridge,'GeckoView:Translations:Translate',{cancelId:randomUUID()}),false);assert.equal(f.state.translations[0].signal.aborted,false);
  assert.equal(await event(f.bridge,'GeckoView:Translations:Translate',{cancelId:id}),true);await assert.rejects(pending);assert.equal(f.state.translations[0].signal.aborted,true);
});
test('actual native bridge only authorizes explicit true and module disable cancels pending work',async()=>{
  const f=bridgeFixture();const pending=event(f.bridge,'GeckoView:Translations:Translate',{requestId:randomUUID(),sourceLanguage:'es',targetLanguage:'en',allowDownload:true});pending.catch(()=>{});await tick();assert.equal(f.state.translations[0].allow,true);
  f.bridge.onDisable();await assert.rejects(pending);assert.equal(f.state.translations[0].signal.aborted,true);
});
test('actual model-management bridge rejects malformed IDs, supports cancellation, and has no cache-download command',async()=>{
  const f=bridgeFixture();await assert.rejects(event(f.settings,'GeckoView:Translations:ManageModel',{operation:'download',operationLevel:'all'}));assert.equal(f.state.downloads.length,0);
  const id=randomUUID();const pending=event(f.settings,'GeckoView:Translations:ManageModel',{requestId:id,operation:'download',operationLevel:'all'});pending.catch(()=>{});await tick();
  assert.equal(await event(f.settings,'GeckoView:Translations:ManageModel',{cancelId:randomUUID()}),false);
  assert.equal(await event(f.settings,'GeckoView:Translations:ManageModel',{cancelId:id}),true);await assert.rejects(pending);
  await assert.rejects(event(f.settings,'GeckoView:Translations:ManageModel',{requestId:randomUUID(),operation:'download',operationLevel:'cache'}));
  assert.equal(f.state.downloads.length,1);
});
test('actual metadata bridge cannot reach explicit download helpers',async()=>{
  const f=bridgeFixture();await event(f.settings,'GeckoView:Translations:TranslationInformation',{});assert.equal(f.state.metadata,1);assert.equal(f.state.downloads.length,0);
});

test('already-aborted and synchronously cancelled operations are observed without stray rejection',async()=>{
  const f=fixture();const cancelled=new AbortController();cancelled.abort();
  await assert.rejects(download(f,[model],cancelled.signal),{name:'AbortError'});
  const controller=new AbortController();await assert.rejects(f.provider.withDownloadOperation(async()=>{controller.abort();throw new Error('stale');},controller.signal));
  await tick();assert.equal(networkRows(f).length,0);
});
test('operation validity is rechecked before starting a queued network request',async()=>{
  const f=fixture();let current=false;
  await assert.rejects(f.provider.withDownloadOperation(op=>f.provider.downloadRecords([model],op),undefined,()=>{if(!current)throw new Error('stale document');}),/stale document/);
  assert.equal(networkRows(f).length,0);
});
test('desktop Parent retains its Remote Settings client and sync subscription',async()=>{
  const f=parentFixture();f.context.AppConstants.platform='linux';let constructed=0,sync=0,gets=0;
  f.modules.RemoteSettings=()=>{constructed++;return {on(event){assert.equal(event,'sync');sync++;},get:async()=>{gets++;return catalog.models.filter(r=>r.sourceLanguage==='es'&&r.targetLanguage==='en'&&r.filter_expression==='');},attachments:{isDownloaded:async()=>false}};};
  assert.ok(await f.Parent.getExpectedTranslationDownloadSize('es','en')>0);
  assert.equal(constructed,1);assert.equal(sync,1);assert.equal(gets,1);assert.equal(f.state.fetches.length,0);
});
test('actual child actor binds pagehide cancellation to its own actor on Android only',async()=>{
  const source='toolkit/components/translations/actors/TranslationsChild.sys.mjs';
  for(const platform of ['android','linux']) {
    const listeners=new Map(),messages=[];
    const context=vm.createContext({AppConstants:{platform},ChromeUtils:{defineESModuleGetters(){}},JSWindowActorChild:class {}});
    const Child=sourceModule(context,source,'TranslationsChild');const child=new Child();
    child.contentWindow={addEventListener:(name,listener)=>listeners.set(name,listener),removeEventListener:name=>listeners.delete(name)};
    child.sendAsyncMessage=name=>messages.push(name);child.actorCreated();
    assert.equal(listeners.has('pagehide'),platform==='android');
    if(platform==='android'){child.handleEvent({type:'pagehide'});assert.deepEqual(messages,['Translations:PageHidden']);}
    child.didDestroy();assert.equal(listeners.size,0);
  }
});

test('cancelling a concurrent second write preserves a previously committed valid cache',async()=>{
  const f=fixture();const controller=new AbortController();
  const first=download(f);const second=download(f,[model],controller.signal);second.catch(()=>{});
  await first;f.state.writeGate=deferred();
  while(f.state.writes.length<2)await tick();controller.abort();
  await assert.rejects(second);f.state.writeGate.resolve();await tick();await tick();
  assert.deepEqual(Buffer.from(f.state.files.get(modelPath)),modelBytes);assert.equal(f.state.files.size,1);
});

test('same-language or invalid requests cannot fetch even catalog metadata',async()=>{
  for(const pair of [{sourceLanguage:'es',targetLanguage:'es'},{sourceLanguage:'bad_tag!',targetLanguage:'en'}]){
    const f=parentFixture();await assert.rejects(f.actor.translateFromUser(pair,true),/Invalid translation language pair/);
    assert.equal(f.state.fetches.length,0);assert.equal(f.translated(),0);
  }
});
test('an unlisted language download cannot report a successful empty operation',async()=>{
  const f=parentFixture();await assert.rejects(f.Parent.downloadLanguageFiles('zz'),/No pinned models/);assert.equal(networkRows(f).length,0);
});

test('actual inference child verifies the WASM and every model expanded payload',async()=>{
  const f=fixture();const c=f.context;c.AppConstants={platform:'android'};c.JSProcessActorChild=class {};
  c.ChromeUtils.defineESModuleGetters=target=>Object.assign(target,{decompressAndroidTranslationAsset:f.decompressAndroidTranslationAsset});
  c.ChromeUtils.defineLazyGetter=(target,key,getter)=>Object.defineProperty(target,key,{get:getter});
  const Child=sourceModule(c,'toolkit/components/translations/actors/TranslationsEngineChild.sys.mjs','TranslationsEngineChild');
  for(const invalid of [false,true]) {
    const child=new Child();child.sendQuery=async()=>({isMocked:false,bergamotWasmBlob:new Blob([wasm]),bergamotWasmRecord:invalid?{...catalog.wasm[0],decompressedHash:'0'.repeat(64)}:catalog.wasm[0],translationModelPayloads:[{languageModelFiles:{vocab:{blob:new Blob([modelBytes]),record:invalid?{...model,decompressedHash:'0'.repeat(64)}:model}}}]});
    if(invalid)await assert.rejects(child.TE_requestEnginePayload({sourceLanguage:'vi',targetLanguage:'en'}),/integrity check failed/);
    else {const payload=await child.TE_requestEnginePayload({sourceLanguage:'vi',targetLanguage:'en'});assert.equal(payload.bergamotWasmArrayBuffer.byteLength,4960506);assert.equal(payload.translationModelPayloads[0].languageModelFiles.vocab.buffer.byteLength,757250);}
  }
});

test('stale document during atomic move rolls back committed bytes without an AbortSignal event',async()=>{
  const f=fixture();f.state.moveGate=deferred();const manager={};let currentWindowGlobal=manager;let captured;
  const result=f.provider.withDownloadOperation(op=>{captured=op;return f.provider.downloadRecords([model],op);},undefined,()=>{
    if(currentWindowGlobal!==manager){assert.equal(captured.controller.signal.aborted,false);throw new Error('stale WindowGlobal');}
  });result.catch(()=>{});
  while(!f.state.movesStarted.length)await tick();currentWindowGlobal={};f.state.moveGate.resolve();
  await assert.rejects(result,/stale WindowGlobal/);assert.equal(f.state.files.size,0);assert.equal(f.state.moves.length,1);
});

test('reviewed WASM4 instantiates with the actual frozen Bergamot glue and native API',async()=>{
  const binary=require('node:zlib').zstdDecompressSync(wasm);
  const c=vm.createContext({WebAssembly,console,performance,TextDecoder,TextEncoder,setTimeout,clearTimeout,Intl});
  const source=fs.readFileSync(path.join(sourceRoot,'toolkit/components/translations/bergamot-translator/bergamot-translator.js'),'utf8');
  vm.runInContext(source+'\nglobalThis.loader=loadBergamot;',c);
  const module=await new Promise((resolve,reject)=>{const instance=c.loader({INITIAL_MEMORY:41943040,wasmBinary:binary,print(){},printErr(){},onAbort:reject,onRuntimeInitialized:()=>queueMicrotask(()=>resolve(instance))});});
  assert.equal(typeof module.TranslationModel,'function');assert.equal(typeof module.AlignedMemory,'function');
  const service=new module.BlockingService({cacheSize:0});service.delete();
});

(async()=>{
  for(const {name,fn} of tests){
    let timer;try {await Promise.race([fn(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('test exceeded 10 seconds')),10000);})]);}
    finally {clearTimeout(timer);}
    console.log('PASS '+name);
  }
  console.log(`${tests.length} actual-source translation asset tests passed; Gecko/UI/inference integration remains separate.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
