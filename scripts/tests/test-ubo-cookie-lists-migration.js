/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';

// LW-M7-41: run the migration JavaScript that patches/android/ubo-cookie-lists-
// migration.patch adds to ExtensionStorageIDB.sys.mjs, taken from the patch's
// own added lines, against a fake storage.local database, pref service and
// extension. Only those boundaries are faked. This does not compile Gecko and
// says nothing about uBO on a device.
//
// usage: node scripts/tests/test-ubo-cookie-lists-migration.js [PATCH]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');

const PATCH = process.argv[2] ||
  path.join(__dirname, '../../patches/android/ubo-cookie-lists-migration.patch');
const added = fs.readFileSync(PATCH, 'utf8').split('\n')
  .filter(line => line.startsWith('+') && !line.startsWith('+++'))
  .map(line => line.slice(1));
const begin = added.findIndex(line => line.startsWith('// Redoubt LW-M7-41 BEGIN'));
const end = added.findIndex(line => line === '// Redoubt LW-M7-41 END');
assert.ok(begin >= 0 && end > begin, 'migration block markers not found in the patch');
const code = added.slice(begin, end + 1).join('\n');

// The hook must sit before setSharedData("storageIDBBackend", true): a child
// context that finds that shared data never asks the parent, so anything
// after it could race uBO's first read.
const text = fs.readFileSync(PATCH, 'utf8');
const hook = text.indexOf('+          .then(() => redoubtMigrateUboCookieLists(extension, storagePrincipal))');
const shared = text.indexOf(' extension.setSharedData("storageIDBBackend", true);');
assert.ok(hook > 0 && shared > hook, 'hook is not chained ahead of setSharedData');
assert.ok(text.slice(0, hook).includes(' promise = migrateJSONFileData(extension, storagePrincipal)'),
  'hook is not on the migrateJSONFileData chain');

// Upstream Extension.sys.mjs announces the backend at startup for every
// migrated or just-installed extension, and a child context that has it never
// calls selectBackend: the hook above would never run (measured on Beta 4).
// While the migration is pending for uBO, the patch's Extension.sys.mjs hunk
// must take a branch ahead of those two that announces nothing.
const extHunk = text.slice(
  text.indexOf('diff --git a/toolkit/components/extensions/Extension.sys.mjs'),
  text.indexOf('diff --git a/toolkit/components/extensions/ExtensionStorageIDB.sys.mjs'));
assert.ok(extHunk.length > 0, 'no Extension.sys.mjs hunk in the patch');
const mustSelect = extHunk.indexOf('+        } else if (lazy.ExtensionStorageIDB.redoubtMustSelectBackend(this)) {');
const migratedBranch = extHunk.indexOf(' } else if (lazy.ExtensionStorageIDB.isMigratedExtension(this)) {');
const disabledBranch = extHunk.indexOf(' if (!lazy.ExtensionStorageIDB.isBackendEnabled) {');
assert.ok(disabledBranch > 0 && mustSelect > disabledBranch && migratedBranch > mustSelect,
  'redoubtMustSelectBackend branch is not between the backend-disabled and migrated branches');
const branchBody = extHunk.slice(mustSelect, migratedBranch);
assert.ok(!branchBody.includes('setSharedData'), 'the pending branch must not announce a backend');
assert.ok(branchBody.includes('setMigratedExtensionPref(this, true)'), 'an install must still set the migrated pref');
assert.ok(text.includes('+  redoubtMustSelectBackend(extension) {\n+    return redoubtUboCookieListsPending(extension);'),
  'ExtensionStorageIDB.redoubtMustSelectBackend does not use the migration predicate');

const UBO = 'uBlock0@raymondhill.net';
const PREF = 'librewolf.uBO.cookieListsMigrated';
const LISTS = ['fanboy-cookiemonster', 'ublock-cookies-easylist'];

function fixture({ stored = {}, id = UBO, temporary = false, prefs = {}, failOpen = false, failSet = false } = {}) {
  const log = [];
  const store = { ...stored };
  const listeners = new Map();
  const errors = [];
  const prefMap = new Map(Object.entries(prefs));
  const extension = Object.assign(new EventEmitter(), {
    id,
    temporarilyInstalled: temporary,
    hasPermission: name => name === 'unlimitedStorage',
  });
  extension.off = extension.removeListener;
  const principal = { tag: 'storage-principal' };
  const ExtensionStorageIDB = {
    async open(storagePrincipal, persisted) {
      assert.equal(storagePrincipal, principal);
      assert.equal(persisted, true);
      log.push('open');
      if (failOpen) throw new Error('open failed');
      let open = true;
      return {
        async get(keys) {
          assert.ok(open);
          assert.deepEqual(Array.from(keys), ['selectedFilterLists']);
          log.push('get');
          const out = {};
          for (const k of keys) if (store[k] !== undefined) out[k] = structuredClone(store[k]);
          return out;
        },
        async set(items) {
          assert.ok(open);
          assert.deepEqual(Object.keys(items), ['selectedFilterLists']);
          log.push('set:start');
          await new Promise(resolve => setImmediate(resolve));
          if (failSet) throw new Error('transaction aborted');
          Object.assign(store, structuredClone(items));
          log.push('set:committed');
        },
        close() { open = false; log.push('close'); },
      };
    },
    addOnChangedListener(extId, fn) {
      if (!listeners.has(extId)) listeners.set(extId, new Set());
      listeners.get(extId).add(fn);
    },
    removeOnChangedListener(extId, fn) { listeners.get(extId).delete(fn); },
  };
  const sandbox = {
    ExtensionStorageIDB,
    Services: {
      prefs: {
        getBoolPref: (name, fallback) => prefMap.has(name) ? prefMap.get(name) : fallback,
        setBoolPref: (name, value) => { log.push(`pref:${name}=${value}`); prefMap.set(name, value); },
      },
    },
    Cu: { reportError: e => errors.push(String(e)) },
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox);
  const run = () => vm.runInContext('redoubtMigrateUboCookieLists', sandbox)(extension, principal);
  const pending = () => vm.runInContext('redoubtUboCookieListsPending', sandbox)(extension);
  const fire = async changes => {
    for (const fn of [...(listeners.get(extension.id) || [])]) fn(changes);
    await settle();
  };
  return { run, pending, fire, log, store, listeners, errors, prefMap, extension };
}

const settle = () => new Promise(resolve => setTimeout(resolve, 10));
const watching = f => (f.listeners.get(f.extension.id)?.size || 0);

const tests = {
  async 'pending (backend left unannounced) only for uBO until the pref is set'() {
    assert.equal(fixture().pending(), true);
    assert.equal(fixture({ prefs: { [PREF]: true } }).pending(), false);
    assert.equal(fixture({ prefs: { [PREF]: false } }).pending(), true);
    assert.equal(fixture({ id: 'other@example.invalid' }).pending(), false);
    assert.equal(fixture({ temporary: true }).pending(), false);
    const f = fixture({ stored: { selectedFilterLists: ['easylist'] } });
    await f.run();
    assert.equal(f.pending(), false, 'still pending after the lists were applied');
    const g = fixture({ stored: { selectedFilterLists: ['easylist'] }, failSet: true });
    await g.run();
    assert.equal(g.pending(), true, 'a failed write must leave the migration pending');
  },

  async 'upgraded profile: both appended once, everything else kept, pref after commit'() {
    const before = ['user-filters', 'ublock-filters', 'easylist', 'https://example.invalid/my.txt'];
    const f = fixture({ stored: { selectedFilterLists: before, hiddenSettings: { x: 1 } } });
    await f.run();
    assert.deepEqual(f.errors, []);
    assert.deepEqual(f.store.selectedFilterLists, [...before, ...LISTS]);
    assert.deepEqual(f.store.hiddenSettings, { x: 1 });
    assert.deepEqual(f.log, ['open', 'get', 'set:start', 'set:committed', `pref:${PREF}=true`, 'close']);
    assert.equal(watching(f), 0);
  },

  async 'second start after apply: pref short-circuits, storage never opened'() {
    const f = fixture({ stored: { selectedFilterLists: ['easylist'] }, prefs: { [PREF]: true } });
    await f.run();
    assert.deepEqual(f.log, []);
    assert.deepEqual(f.store.selectedFilterLists, ['easylist']);
  },

  async 'opt-out after migration is kept: user removed both, pref set, nothing re-added'() {
    const f = fixture({ stored: { selectedFilterLists: ['ublock-filters'] }, prefs: { [PREF]: true } });
    await f.run();
    await f.run();
    assert.deepEqual(f.store.selectedFilterLists, ['ublock-filters']);
    assert.deepEqual(f.log, []);
  },

  async 'idempotent if the pref write was lost: lists already there, no write'() {
    const f = fixture({ stored: { selectedFilterLists: ['easylist', ...LISTS] } });
    await f.run();
    assert.deepEqual(f.store.selectedFilterLists, ['easylist', ...LISTS]);
    assert.deepEqual(f.log, ['open', 'get', `pref:${PREF}=true`, 'close']);
  },

  async 'one list selected: user choice, no write, pref set'() {
    for (const kept of LISTS) {
      const f = fixture({ stored: { selectedFilterLists: ['easylist', kept] } });
      await f.run();
      assert.deepEqual(f.store.selectedFilterLists, ['easylist', kept]);
      assert.ok(!f.log.includes('set:start'));
      assert.equal(f.prefMap.get(PREF), true);
    }
  },

  async 'empty selection gets both'() {
    const f = fixture({ stored: { selectedFilterLists: [] } });
    await f.run();
    assert.deepEqual(f.store.selectedFilterLists, LISTS);
    assert.equal(f.prefMap.get(PREF), true);
  },

  async 'other extensions and temporary uBO are never touched'() {
    for (const options of [{ id: 'other@example.invalid' }, { temporary: true }]) {
      const f = fixture({ ...options, stored: { selectedFilterLists: ['easylist'] } });
      await f.run();
      assert.deepEqual(f.log, []);
      assert.deepEqual(f.store.selectedFilterLists, ['easylist']);
    }
  },

  async 'unexpected stored shape: left alone, pref unset'() {
    for (const value of ['easylist', { a: 1 }, ['easylist', 3], null]) {
      const f = fixture({ stored: { selectedFilterLists: value } });
      await f.run();
      assert.ok(!f.log.includes('set:start'));
      assert.equal(f.prefMap.has(PREF), false);
      assert.deepEqual(f.store.selectedFilterLists, value);
    }
  },

  async 'failed write: never rejects, pref unset, error reported, db closed'() {
    const f = fixture({ stored: { selectedFilterLists: ['easylist'] }, failSet: true });
    await f.run();
    assert.equal(f.prefMap.has(PREF), false);
    assert.equal(f.errors.length, 1);
    assert.equal(f.log.at(-1), 'close');
  },

  async 'failed open: never rejects, pref unset'() {
    const f = fixture({ stored: { selectedFilterLists: ['easylist'] }, failOpen: true });
    await f.run();
    assert.equal(f.prefMap.has(PREF), false);
    assert.equal(f.errors.length, 1);
  },

  async 'fresh online install: first selection has the lists, migration done for good'() {
    const f = fixture();
    await f.run();
    assert.deepEqual(f.log, ['open', 'get', 'close']);
    assert.equal(watching(f), 1);
    await f.fire({ hiddenSettings: {} });
    assert.equal(watching(f), 1, 'an unrelated write must not end the watch');
    f.store.selectedFilterLists = ['ublock-filters', ...LISTS];
    await f.fire({ selectedFilterLists: { newValue: 'serialised' } });
    assert.equal(watching(f), 0);
    assert.equal(f.prefMap.get(PREF), true);
    assert.ok(!f.log.includes('set:start'));
    // The user turns both off in that first session; the next start keeps it.
    f.store.selectedFilterLists = ['ublock-filters'];
    await f.run();
    assert.deepEqual(f.store.selectedFilterLists, ['ublock-filters']);
  },

  async 'fresh offline install: no write while uBO runs, next start applies'() {
    const f = fixture();
    await f.run();
    f.store.selectedFilterLists = ['ublock-filters'];
    await f.fire({ selectedFilterLists: {} });
    assert.equal(watching(f), 0);
    assert.ok(!f.log.includes('set:start'));
    assert.equal(f.prefMap.has(PREF), false);
    await f.run();
    assert.deepEqual(f.store.selectedFilterLists, ['ublock-filters', ...LISTS]);
    assert.equal(f.prefMap.get(PREF), true);
  },

  async 'fresh install that shuts down before choosing: watch removed, nothing recorded'() {
    const f = fixture();
    await f.run();
    assert.equal(f.extension.listenerCount('shutdown'), 1);
    f.extension.emit('shutdown');
    assert.equal(watching(f), 0);
    assert.equal(f.extension.listenerCount('shutdown'), 0);
    assert.equal(f.prefMap.has(PREF), false);
  },
};

(async () => {
  for (const [name, fn] of Object.entries(tests)) {
    await fn();
    console.log(`PASS ${name}`);
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
