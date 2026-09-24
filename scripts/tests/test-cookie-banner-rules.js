/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';

// Execute the actual patched service, hash utility and vendored schema validator.
// Only Gecko module/platform/native boundaries are faked. This is not a browser
// action test: no assertion here claims that a banner was rejected on a page.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const sourceRoot = process.argv[2];
assert.ok(sourceRoot, 'usage: node scripts/tests/test-cookie-banner-rules.js PATCHED_SOURCE');
const read = name => fs.readFileSync(path.join(sourceRoot, name), 'utf8');
const serviceSource = read('toolkit/components/cookiebanners/CookieBannerListService.sys.mjs');
const sharedSource = read('services/settings/SharedUtils.sys.mjs');
const schemaSource = read('third_party/js/cfworker/json-schema.js');
const snapshotBytes = fs.readFileSync(path.join(sourceRoot, 'services/settings/dumps/main/cookie-banner-rules-list.json'));
const snapshot = JSON.parse(snapshotBytes);
const schema = JSON.parse(read('toolkit/components/cookiebanners/schema/CookieBannerRule.schema.json'));
const SNAPSHOT_URL = 'resource://app/defaults/settings/main/cookie-banner-rules-list.json';
const SCHEMA_URL = 'chrome://global/content/cookiebanners/CookieBannerRule.schema.json';
const SKIP_PREF = 'cookiebanners.listService.testSkipRemoteSettings';
const RULES_PREF = 'cookiebanners.listService.testRules';
const clone = value => JSON.parse(JSON.stringify(value));
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
const fixtureRule = (id = 'fixture') => ({ id, domains: ['example.org'], click: { presence: '#banner', optOut: '#reject' } });

function fixture({ platform = 'android', bytes = snapshotBytes, fetchError, missing = false, rules = [], schemaGate, snapshotGate } = {}) {
  const validatorContext = vm.createContext({ URL });
  vm.runInContext(schemaSource, validatorContext, { filename: 'cfworker/json-schema.js' });
  const sharedContext = vm.createContext({ crypto: webcrypto, Uint8Array });
  vm.runInContext(sharedSource.replace('export var SharedUtils', 'var SharedUtils'), sharedContext);
  const state = {
    normal: 1, private: 1, inserted: [], removed: [], rules: new Map(), fetches: [],
    remoteConstructed: 0, remoteGets: 0, remoteOn: 0, remoteOff: 0,
    prefs: new Map(), observers: new Map(), resets: [], errors: [],
  };
  const schemaRequested = deferred();
  const snapshotRequested = deferred();
  const remote = {
    async get() { state.remoteGets++; return clone(rules); },
    on(event, callback) { assert.equal(event, 'sync'); state.remoteOn++; this.callback = callback; },
    off(event, callback) { assert.equal(event, 'sync'); assert.equal(callback, this.callback); state.remoteOff++; },
  };
  class Rule {
    constructor() { this.cookiesOptOut = []; this.cookiesOptIn = []; this.clickRule = null; }
    addCookie(optOut, name, value, host, cookiePath, expiryRelative, unsetValue, isSecure, isHTTPOnly, isSession, sameSite, schemeMap) {
      this[optOut ? 'cookiesOptOut' : 'cookiesOptIn'].push({ cookie: { name, value, host, path: cookiePath, expiryRelative, unsetValue, isSecure, isHTTPOnly, isSession, sameSite, schemeMap } });
    }
    addClickRule(presence, skipPresenceVisibilityCheck, runContext, hide, optOut, optIn) {
      this.clickRule = { presence, skipPresenceVisibilityCheck, runContext, hide, optOut, optIn };
    }
  }
  const modules = {
    AppConstants: { platform },
    SharedUtils: sharedContext.SharedUtils,
    JsonSchema: { Validator: validatorContext.Validator },
    RemoteSettings: collection => { assert.equal(collection, 'cookie-banner-rules-list'); state.remoteConstructed++; return remote; },
  };
  const services = {
    prefs: {
      prefHasUserValue: key => state.prefs.has(key),
      addObserver(key, observer) {
        if (!state.observers.has(key)) state.observers.set(key, new Set());
        assert.ok(!state.observers.get(key).has(observer), 'observer must not be registered twice');
        state.observers.get(key).add(observer);
      },
      removeObserver(key, observer) { assert.ok(state.observers.get(key)?.delete(observer), 'remove only a registered observer'); },
    },
    cookieBanners: {
      get isEnabled() { return state.normal !== 0 || state.private !== 0; },
      insertRule(rule) { state.inserted.push(rule); state.rules.set(rule.id, rule); },
      removeRule(rule) { state.removed.push(rule); state.rules.delete(rule.id); },
      resetRules() { state.rules.clear(); },
      removeAllExecutedRecords(isPrivate) { state.resets.push(isPrivate); },
    },
  };
  const context = vm.createContext({
    URL, TextDecoder, Uint8Array, Services: services,
    Components: { ID: value => value },
    Ci: { nsIClickRule: { RUN_TOP: 0, RUN_CHILD: 1, RUN_ALL: 2 } },
    Cc: { '@mozilla.org/cookie-banner-rule;1': { createInstance: () => new Rule() } },
    ChromeUtils: {
      generateQI: () => () => {},
      defineESModuleGetters(object, mapping) {
        for (const name of Object.keys(mapping)) Object.defineProperty(object, name, { get: () => modules[name] });
      },
      defineLazyGetter(object, name, getter) {
        Object.defineProperty(object, name, { configurable: true, get() {
          const value = getter(); Object.defineProperty(object, name, { value }); return value;
        } });
      },
    },
    XPCOMUtils: { defineLazyPreferenceGetter(object, name, key) {
      Object.defineProperty(object, name, { get: () => state.prefs.get(key) ?? (name === 'DEFAULT_EXPIRY_RELATIVE' ? 31536000 : name === 'testRulesPref' ? '[]' : false) });
    } },
    console: { createInstance: () => ({ debug() {}, warn() {}, error(...args) { state.errors.push(args); } }) },
    async fetch(url) {
      state.fetches.push(url);
      if (url === SCHEMA_URL) {
        schemaRequested.resolve();
        if (schemaGate) await schemaGate.promise;
        return { ok: true, async json() { return clone(schema); } };
      }
      assert.equal(url, SNAPSHOT_URL, 'only the fixed packaged snapshot may be fetched');
      snapshotRequested.resolve();
      if (snapshotGate) await snapshotGate.promise;
      if (fetchError) throw new Error('fixture fetch failure');
      return { ok: !missing, async arrayBuffer() { return Uint8Array.from(bytes).buffer; } };
    },
  });
  const executable = serviceSource
    .replace('import { XPCOMUtils } from "resource://gre/modules/XPCOMUtils.sys.mjs";', '')
    .replace('export class CookieBannerListService', 'class CookieBannerListService');
  assert.ok(!executable.includes('export class') && executable.includes('async function validateAndroidRules'));
  vm.runInContext(executable + '\nthis.Service = CookieBannerListService; this.validateSnapshot = validateAndroidRules;', context, { filename: 'CookieBannerListService.sys.mjs' });
  const service = new context.Service();
  const setPref = (key, value) => {
    state.prefs.set(key, value);
    for (const observer of state.observers.get(key) || []) observer.observe(null, 'nsPref:changed', key);
  };
  const assertNoRemote = () => {
    assert.equal(state.remoteConstructed, 0); assert.equal(state.remoteGets, 0);
    assert.equal(state.remoteOn, 0); assert.equal(state.remoteOff, 0);
    assert.ok(state.fetches.every(url => url === SNAPSHOT_URL || url === SCHEMA_URL));
  };
  const assertNoObservers = () => assert.ok([...state.observers.values()].every(values => !values.size));
  return { state, service, context, remote, setPref, assertNoRemote, assertNoObservers, schemaRequested, snapshotRequested };
}

let passed = 0;
async function test(name, run) {
  let timer;
  try {
    await Promise.race([run(), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('test timeout: ' + name)), 5000); })]);
    passed++; process.stdout.write('PASS ' + name + '\n');
  } finally { clearTimeout(timer); }
}
(async () => {
  await test('actual pinned snapshot imports all 558 unique rules without any Remote Settings client', async () => {
    const f = fixture(); await f.service.initForTest();
    assert.equal(f.state.rules.size, 558); assert.equal(f.state.inserted.length, 558);
    const rule = [...f.state.rules.values()].find(r => r.domains.includes('duh.de'));
    assert.equal(rule.cookiesOptOut[0].cookie.name, 'cookie_dismiss');
    assert.equal(rule.cookiesOptOut[0].cookie.value, 'true');
    assert.ok(f.state.rules.has('disabled'));
    assert.equal([...f.state.rules.values()].filter(r => r.domains.length === 0).length, 9);
    f.assertNoRemote(); f.service.shutdown(); f.assertNoObservers();
  });
  for (const [name, options] of [
    ['missing file', { missing: true }], ['fetch failure', { fetchError: true }],
    ['truncated file', { bytes: snapshotBytes.subarray(1) }],
    ['same-size corruption', { bytes: Buffer.from(snapshotBytes).fill(32, 100, 101) }],
  ]) await test(name + ' rejects initialization before inserting rules or observers', async () => {
    const f = fixture(options); await assert.rejects(f.service.initForTest());
    assert.equal(f.state.inserted.length, 0); f.assertNoObservers(); f.assertNoRemote();
  });
  await test('actual schema validator accepts the complete reviewed snapshot', async () => {
    const f = fixture(); const result = await f.context.validateSnapshot(clone(snapshot));
    assert.equal(result.length, 558); assert.ok(!('schema' in result[0])); assert.ok(!('last_modified' in result[0]));
    f.assertNoRemote();
  });
  for (const [name, mutate] of [
    ['wrong timestamp', value => value.timestamp++],
    ['wrong count', value => value.data.pop()],
    ['unknown envelope field', value => { value.unreviewed = true; }],
    ['duplicate rule ID', value => { value.data[1].id = value.data[0].id; }],
    ['invalid rule shape', value => { value.data[0].domains = 'example.org'; }],
    ['unknown rule field', value => { value.data[0].unreviewed = true; }],
    ['missing metadata', value => { delete value.data[0].schema; }],
    ['unsupported targeting', value => { value.data[0].filter_expression = 'env.channel == "nightly"'; }],
  ]) await test(name + ' is rejected by the production snapshot validator', async () => {
    const f = fixture(); const value = clone(snapshot); mutate(value);
    await assert.rejects(f.context.validateSnapshot(value)); assert.equal(f.state.inserted.length, 0);
  });
  await test('shutdown during snapshot load prevents insertion and observer registration', async () => {
    const gate = deferred(); const f = fixture({ snapshotGate: gate }); const pending = f.service.initForTest();
    await f.snapshotRequested.promise; f.service.shutdown(); gate.resolve(); await pending;
    assert.equal(f.state.inserted.length, 0); f.assertNoObservers(); f.assertNoRemote();
  });
  await test('old load cannot insert into a newly initialized lifecycle', async () => {
    const gate = deferred(); const f = fixture({ schemaGate: gate }); const old = f.service.initForTest();
    await f.schemaRequested.promise; f.service.shutdown();
    const current = f.service.initForTest(); gate.resolve(); await Promise.all([old, current]);
    assert.equal(f.state.inserted.length, 558); assert.equal(f.state.rules.size, 558);
    f.service.shutdown(); f.assertNoObservers(); f.assertNoRemote();
  });
  await test('test rule schema completion after shutdown cannot insert stale test rules', async () => {
    const gate = deferred(); const f = fixture({ schemaGate: gate });
    f.setPref(SKIP_PREF, true); f.setPref(RULES_PREF, JSON.stringify([fixtureRule('old')]));
    const old = f.service.initForTest(); await f.schemaRequested.promise; f.service.shutdown();
    f.setPref(RULES_PREF, JSON.stringify([fixtureRule('current')])); const current = f.service.initForTest();
    gate.resolve(); await Promise.all([old, current]);
    assert.deepEqual([...f.state.rules.keys()], ['current']); f.assertNoRemote();
  });
  await test('normal-only and private-only enabled services can initialize and both-disabled cannot import', async () => {
    for (const [normal, privateMode, expected] of [[1, 0, 558], [0, 1, 558], [0, 0, 0]]) {
      const f = fixture(); f.state.normal = normal; f.state.private = privateMode;
      await f.service.initForTest(); assert.equal(f.state.rules.size, expected);
      f.service.shutdown(); f.assertNoObservers(); f.assertNoRemote();
    }
  });
  await test('repeated init registers observers once and shutdown/reinit reloads the snapshot', async () => {
    const f = fixture(); await Promise.all([f.service.initForTest(), f.service.initForTest()]);
    assert.equal(f.state.rules.size, 558); assert.equal(f.state.inserted.length, 558);
    await f.service.initForTest(); assert.equal(f.state.rules.size, 558);
    f.service.shutdown(); f.state.rules.clear(); await f.service.initForTest();
    assert.equal(f.state.rules.size, 558); f.service.shutdown(); f.assertNoObservers(); f.assertNoRemote();
  });
  await test('test override skips packaged data and rejects invalid rules without Remote Settings', async () => {
    const f = fixture(); f.setPref(SKIP_PREF, true);
    f.setPref(RULES_PREF, JSON.stringify([fixtureRule(), { ...fixtureRule('invalid'), click: { presence: '#banner', runContext: 'invalid' } }]));
    await f.service.initForTest(); assert.deepEqual([...f.state.rules.keys()], ['fixture']);
    assert.ok(!f.state.fetches.includes(SNAPSHOT_URL)); f.assertNoRemote();
  });
  await test('concurrent test-pref reloads keep only the latest rules and reset both execution contexts', async () => {
    const f = fixture(); f.setPref(SKIP_PREF, true); await f.service.initForTest();
    f.setPref(RULES_PREF, JSON.stringify([fixtureRule('old')]));
    f.setPref(RULES_PREF, JSON.stringify([fixtureRule('current')])); await tick();
    assert.deepEqual([...f.state.rules.keys()], ['current']);
    assert.deepEqual(f.state.resets, [false, true, false, true]); f.assertNoRemote();
  });
  await test('Android ignores a synthetic Remote Settings sync event', async () => {
    const f = fixture(); await f.service.initForTest();
    f.service.onSync({ data: { created: [fixtureRule()], updated: [], deleted: [] } });
    assert.equal(f.state.rules.size, 558); assert.ok(!f.state.rules.has('fixture')); f.assertNoRemote();
  });
  await test('desktop still imports Remote Settings and applies sync events including legacy conversion', async () => {
    const rule = fixtureRule('desktop'); rule.click.runContext = 'old-unknown-value';
    const f = fixture({ platform: 'linux', rules: [rule] }); await f.service.initForTest();
    assert.equal(f.state.remoteConstructed, 1); assert.equal(f.state.remoteGets, 1); assert.equal(f.state.remoteOn, 1);
    assert.equal(f.state.fetches.length, 0); assert.equal(f.state.rules.get('desktop').clickRule.runContext, 0);
    f.remote.callback({ data: { created: [fixtureRule('new')], updated: [], deleted: [rule] } });
    assert.ok(f.state.rules.has('new')); assert.ok(!f.state.rules.has('desktop'));
    f.service.shutdown(); assert.equal(f.state.remoteOff, 1); f.assertNoObservers();
  });
  process.stdout.write(`${passed} actual-source cookie-banner loader tests passed; native rejection is NOT tested here.\n`);
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
