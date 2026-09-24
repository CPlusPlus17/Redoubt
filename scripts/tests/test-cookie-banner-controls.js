/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';

// Execute the real GeckoView event handler. Native service/platform boundaries
// are faked: these assertions prove routing and callback outcomes, not eTLD
// storage durability, private teardown, or actual banner rejection.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(process.argv[2], 'mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs'), 'utf8');
function fixture() {
  const calls = [];
  const modes = { normal: 1, private: 1 };
  const state = { calls, modes, fail: null, domainMode: -1, generation: "1", active: true };
  const service = {
    get privateSessionToken() { if (!state.active) throw new Error("NS_ERROR_NOT_AVAILABLE"); return state.generation; },
    setDomainPrefForPrivateSession(uri, mode, token) {
      calls.push(['scoped-set', uri, mode, token]);
      if (!state.active || token !== state.generation) throw new Error("NS_ERROR_NOT_AVAILABLE");
    },
    removeDomainPrefForPrivateSession(uri, token) {
      calls.push(['scoped-remove', uri, token]);
      if (!state.active || token !== state.generation) throw new Error("NS_ERROR_NOT_AVAILABLE");
    },
    setDomainPref(...args) { calls.push(['set', ...args]); if (state.fail) throw state.fail; },
    removeDomainPref(...args) { calls.push(['remove', ...args]); if (state.fail) throw state.fail; },
    getDomainPref(...args) { calls.push(['get', ...args]); if (state.fail) throw state.fail; return state.domainMode; },
    setDomainPrefAndPersistInPrivateBrowsing(...args) { calls.push(['persistent-private', ...args]); if (state.fail) throw state.fail; },
  };
  const ci = new Proxy({ nsICookieBannerService: { MODE_DISABLED: 0, MODE_UNSET: -1 } }, {
    get(target, key) { return target[key] || new Proxy({}, { get() { return 0; } }); },
  });
  const context = vm.createContext({
    Ci: ci,
    Services: {
      io: { newURI(uri) { const url = new URL(uri); if (!['http:', 'https:'].includes(url.protocol)) throw new Error('unsupported URI'); return uri; } },
      cookieBanners: service,
      clearData: new Proxy({}, { get() { throw new Error('site data clearing is forbidden in banner events'); } }),
    },
    ChromeUtils: { defineESModuleGetters() {} },
    XPCOMUtils: {
      defineLazyPreferenceGetter(target, name, pref) {
        Object.defineProperty(target, name, { get() { return modes[pref.endsWith('privateBrowsing') ? 'private' : 'normal']; } });
      },
    },
    GeckoViewUtils: { initLogging() { return { debug() {}, warn() {} }; } },
  });
  const transformed = source.replace(/^import .*;\n/gm, '').replace('export const GeckoViewStorageController', 'const GeckoViewStorageController');
  vm.runInContext(transformed + '\nthis.controller = GeckoViewStorageController;', context);
  state.event = (name, data) => {
    const results = [];
    context.controller.onEvent('GeckoView:' + name, data, {
      onSuccess(value) { results.push(['success', value]); },
      onError(error) { results.push(['error', error]); },
    });
    assert.equal(results.length, 1, 'exactly one terminal callback');
    return results[0];
  };
  return state;
}
let passed = 0;
function test(name, action) { action(); passed++; process.stdout.write('PASS ' + name + '\n'); }
for (const privateMode of [false, true]) {
  test('set acknowledges correct ' + (privateMode ? 'temporary private' : 'normal') + ' scope', () => {
    const f = fixture();
    assert.equal(f.event('SetCookieBannerModeForDomain', { uri: 'https://sub.example.org/path', mode: 0, isPrivateBrowsing: privateMode })[0], 'success');
    assert.deepEqual(f.calls, [['set', 'https://sub.example.org/path', 0, privateMode]]);
  });
  test('remove acknowledges correct ' + (privateMode ? 'private' : 'normal') + ' scope', () => {
    const f = fixture();
    assert.equal(f.event('RemoveCookieBannerModeForDomain', { uri: 'http://example.org/path', isPrivateBrowsing: privateMode })[0], 'success');
    assert.deepEqual(f.calls, [['remove', 'http://example.org/path', privateMode]]);
  });
  test('unset domain inherits only its corresponding global mode ' + privateMode, () => {
    const f = fixture(); f.modes.normal = privateMode ? 0 : 1; f.modes.private = privateMode ? 1 : 0;
    assert.equal(f.event('GetCookieBannerModeForDomain', { uri: 'https://example.org', isPrivateBrowsing: privateMode })[1].mode, 1);
    f.domainMode = 0;
    assert.equal(f.event('GetCookieBannerModeForDomain', { uri: 'https://example.org', isPrivateBrowsing: privateMode })[1].mode, 0);
  });
}
for (const event of ['SetCookieBannerModeForDomain', 'RemoveCookieBannerModeForDomain', 'GetCookieBannerModeForDomain']) {
  test(event + ' native failure terminates with an error', () => {
    const f = fixture(); f.fail = new Error('native failure');
    const result = f.event(event, { uri: 'https://example.org', mode: 0, isPrivateBrowsing: false });
    assert.equal(result[0], 'error'); assert.match(result[1], /native failure/);
  });
  test(event + ' invalid URI terminates before native mutation', () => {
    const f = fixture();
    assert.equal(f.event(event, { uri: 'about:config', mode: 0, isPrivateBrowsing: false })[0], 'error');
    assert.equal(f.calls.length, 0);
  });
}
test('globally disabled query preserves domain exceptions without querying native storage', () => {
  const f = fixture(); f.modes.normal = 0;
  assert.equal(f.event('GetCookieBannerModeForDomain', { uri: 'https://example.org', isPrivateBrowsing: false })[1].mode, 0);
  assert.equal(f.calls.length, 0);
});
test('token acquisition reports inactive native session errors', () => {
  const f = fixture();
  assert.deepEqual(f.event('GetCookieBannerPrivateSessionToken', {}), ['success', '1']);
  f.active = false;
  assert.equal(f.event('GetCookieBannerPrivateSessionToken', {})[0], 'error');
});
for (const event of ['SetCookieBannerModeForDomain', 'RemoveCookieBannerModeForDomain']) {
  test(event + ' forwards immutable private token to native scoped API', () => {
    const f = fixture();
    const data = { uri: 'https://example.org', mode: 0, isPrivateBrowsing: true, privateSessionToken: '1' };
    assert.equal(f.event(event, data)[0], 'success');
    assert.equal(f.calls[0][0], event.startsWith('Set') ? 'scoped-set' : 'scoped-remove');
    assert.equal(f.calls[0].at(-1), '1');
    f.generation = '2';
    assert.equal(f.event(event, data)[0], 'error');
    assert.equal(f.calls[1].at(-1), '1', 'old capability must not silently refresh');
  });
  test(event + ' rejects a private token masquerading as a normal choice', () => {
    const f = fixture();
    assert.equal(f.event(event, { uri: 'https://example.org', mode: 0, isPrivateBrowsing: false, privateSessionToken: '1' })[0], 'error');
    assert.equal(f.calls.length, 0);
  });
}
test('stale scoped read rejects before native preference access', () => {
  const f = fixture(); f.generation = '2';
  assert.equal(f.event('GetCookieBannerModeForDomain', { uri: 'https://example.org', isPrivateBrowsing: true, privateSessionToken: '1' })[0], 'error');
  assert.equal(f.calls.length, 0);
});
console.log('PASS ' + passed + ' actual-JS event tests; native lifetime and banner behavior remain target gates');
