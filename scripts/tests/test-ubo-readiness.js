/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */
'use strict';

// Execute the actual patched Gecko registration/wait functions, with only the
// platform event, timer and add-on boundaries faked. Requires a patched source
// tree; this does not substitute for compiling GeckoView or first-page APK tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');
const root = process.argv[2];
assert.ok(root, 'usage: node scripts/tests/test-ubo-readiness.js PATCHED_SOURCE');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const web = read('toolkit/components/extensions/parent/ext-webRequest.js');
const gv = read('mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs');
const registrar = web.slice(web.indexOf('function registerEvent('), web.indexOf('function makeWebRequestEventAPI('));
const waitMethod = gv.slice(gv.indexOf('  async awaitBlockingResponseListener('), gv.indexOf('  async uninstallWebExtension('));
assert.ok(registrar.startsWith('function registerEvent('));
assert.ok(waitMethod.includes('30000'));

// A hung wait leaves no pending timer, so Node would exit 0 without reaching
// the summary. Only the completed run below may report success.
process.exitCode = 1;

function fixture({ active = true, permission = true, version = '1.74.0' } = {}) {
  const granted = { permission };
  const extension = Object.assign(new EventEmitter(), {
    id: 'uBlock0@raymondhill.net',
    hasPermission: name => granted.permission && name === 'webRequestBlocking',
  });
  const addon = { isActive: active, version };
  const policy = { extension };
  const policies = new Map([[extension.id, policy]]);
  const timers = new Map();
  let nextTimer = 0;
  const listeners = new Map();
  const warnings = [];
  const sandbox = {
    WebRequest: new Proxy({}, {
      get: (_, event) => ({
        addListener: listener => {
          if (!listeners.has(event)) listeners.set(event, new Set());
          listeners.get(event).add(listener);
        },
        removeListener: listener => listeners.get(event)?.delete(listener),
      }),
    }),
    Cu: { reportError: warning => warnings.push(warning) },
    WebExtensionPolicy: { getByID: id => policies.get(id) },
    lazy: {
      setTimeout: (callback, milliseconds) => {
        assert.equal(milliseconds, 30000);
        timers.set(++nextTimer, callback);
        return nextTimer;
      },
      clearTimeout: id => timers.delete(id),
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(registrar, sandbox);
  const controller = vm.runInContext('({' + waitMethod + '})', sandbox);
  controller.extensionById = async id => id === extension.id ? addon : null;
  // 153.0esr's registerEvent took a remoteTab before the Redoubt flag; 153.3esr dropped it.
  const liveArgs = live => registrar.includes('remoteTab = null') ? [null, live] : [live];
  const register = (event = 'onHeadersReceived', blocking = true, live = true) =>
    sandbox.registerEvent(extension, event, {}, {}, blocking ? ['blocking'] : [], ...liveArgs(live));
  let nextRequest = 0;
  const wait = (expected = '1.74.0', requestId) => controller.awaitBlockingResponseListener(
    extension.id, expected,
    requestId || `00000000-0000-4000-8000-${String(++nextRequest).padStart(12, '0')}`,
  );
  const cancel = (requestId, id = extension.id, expected = '1.74.0') =>
    controller.cancelBlockingResponseListener(id, expected, requestId);
  const clean = () => {
    assert.equal(timers.size, 0, 'timer cleaned');
    assert.equal(controller.blockingResponseWaiters?.size || 0, 0, 'active request cleaned');
    assert.equal(extension.listenerCount('shutdown'), 0, 'shutdown listener cleaned');
    assert.equal(extension.listenerCount('redoubt-blocking-response-listener'), 0, 'readiness listener cleaned');
    assert.equal(extension.listenerCount('ready'), 0, 'startup listener cleaned');
  };
  // ext-backgroundPage.js at APP_STARTUP: primeBackground() primes persisted
  // listeners and registers the one-shot start handler, which Gecko itself
  // only answers after the first browser window paints.
  const primeDelayedBackground = () => {
    extension.backgroundState = 'stopped';
    extension.promiseBackgroundStarted = () => new Promise(() => {});
    const primed = register('onHeadersReceived', true, false);
    const started = { count: 0 };
    extension.once('start-background-script', () => {
      started.count++;
      extension.backgroundState = 'starting';
      // uBO re-registers its blocking listener once its filters are loaded.
      setImmediate(() => primed.convert({}, { xulBrowser: { frameLoader: { remoteTab: {} } } }));
    });
    return started;
  };
  const grant = value => { granted.permission = value; };
  return { extension, addon, policies, timers, register, wait, cancel, clean, warnings, controller,
    primeDelayedBackground, grant };
}
const tick = async () => { await Promise.resolve(); await Promise.resolve(); };
let passed = 0;
async function test(name, run) { await run(); passed++; process.stdout.write('PASS ' + name + '\n'); }
(async () => {
  const requestA = '10000000-0000-4000-8000-000000000001';
  const requestB = '10000000-0000-4000-8000-000000000002';
  await test('cancel during asynchronous lookup cannot later attach listeners', async () => {
    const f = fixture(); let release;
    f.controller.extensionById = () => new Promise(resolve => { release = resolve; });
    const result = f.wait('1.74.0', requestA);
    const checked = assert.rejects(result, /cancelled/);
    assert.equal(f.cancel(requestA), true);
    f.clean();
    release(f.addon); await checked; await tick(); f.clean();
    f.register(); await tick(); f.clean();
  });
  await test('cancel active wait releases timers and both event listeners immediately', async () => {
    const f = fixture(); const result = f.wait('1.74.0', requestA);
    const checked = assert.rejects(result, /cancelled/);
    await tick();
    assert.equal(f.extension.listenerCount('shutdown'), 1);
    assert.equal(f.cancel(requestA), true);
    f.clean(); await checked;
    assert.equal(f.cancel(requestA), false);
  });
  await test('cancellation is bound to request ID extension ID and version', async () => {
    const f = fixture(); let settled = false;
    const result = f.wait('1.74.0', requestA).then(() => { settled = true; });
    await tick();
    assert.equal(f.cancel(requestB), false);
    assert.equal(f.cancel(requestA, 'other@example.invalid'), false);
    assert.equal(f.cancel(requestA, f.extension.id, '1.75.0'), false);
    await tick(); assert.equal(settled, false);
    f.register(); await result; f.clean();
  });
  await test('completed request cannot be cancelled or reused to target a later waiter', async () => {
    const f = fixture(); const first = f.register();
    await f.wait('1.74.0', requestA); f.clean();
    assert.equal(f.cancel(requestA), false);
    await assert.rejects(f.wait('1.74.0', requestA), /already used/);
    first.unregister();
    let settled = false;
    const future = f.wait('1.74.0', requestB).then(() => { settled = true; });
    await tick();
    assert.equal(f.cancel(requestA), false);
    await tick(); assert.equal(settled, false);
    f.register(); await future; f.clean();
  });
  await test('unknown cancellation does not reserve or poison a future request ID', async () => {
    const f = fixture();
    assert.equal(f.cancel(requestA), false);
    f.register(); await f.wait('1.74.0', requestA); f.clean();
  });
  await test('cancelled request ID cannot be reused', async () => {
    const f = fixture(); const result = f.wait('1.74.0', requestA);
    const checked = assert.rejects(result, /cancelled/);
    assert.equal(f.cancel(requestA), true); await checked; f.clean();
    await assert.rejects(f.wait('1.74.0', requestA), /already used/); f.clean();
  });
  await test('invalid request ID fails without registering cancellation or timer state', async () => {
    const f = fixture();
    await assert.rejects(f.wait('1.74.0', 'bad-id'), /Invalid/); f.clean();
  });
  await test('already active live blocking listener resolves', async () => {
    const f = fixture(); f.register(); await f.wait(); f.clean();
  });
  await test('startup and primed listeners cannot release navigation barrier', async () => {
    const f = fixture(); let settled = false;
    const result = f.wait().then(() => { settled = true; });
    await tick(); f.extension.emit('ready'); f.extension.emit('background-page-event');
    const registration = f.register('onHeadersReceived', true, false);
    await tick(); assert.equal(settled, false);
    registration.convert({}, { xulBrowser: { frameLoader: { remoteTab: {} } } });
    await result; assert.equal(settled, true); f.clean();
  });
  await test('other and nonblocking listeners cannot satisfy barrier', async () => {
    const f = fixture(); let settled = false;
    const result = f.wait().then(() => { settled = true; });
    await tick(); f.register('onBeforeRequest'); f.register('onHeadersReceived', false);
    await tick(); assert.equal(settled, false);
    f.register(); await result; f.clean();
  });
  await test('unregistered listener is not retained as readiness', async () => {
    const f = fixture(); const first = f.register(); first.unregister();
    let settled = false; const result = f.wait().then(() => { settled = true; });
    await tick(); assert.equal(settled, false);
    f.register(); await result; f.clean();
  });
  await test('multiple listeners are counted independently', async () => {
    const f = fixture(); const first = f.register(); const second = f.register();
    first.unregister(); await f.wait(); f.clean();
    second.unregister(); assert.equal(f.extension.redoubtBlockingResponseListeners.size, 0);
  });
  await test('disabled extension and wrong version reject', async () => {
    const disabled = fixture({ active: false }); disabled.register();
    await assert.rejects(disabled.wait(), /No matching active/); disabled.clean();
    const mismatch = fixture(); mismatch.register();
    await assert.rejects(mismatch.wait('0.0'), /No matching active/); mismatch.clean();
  });
  await test('missing permission cannot create an approved blocking marker', async () => {
    const f = fixture({ permission: false }); f.register();
    assert.equal(f.extension.redoubtBlockingResponseListeners, undefined);
    assert.equal(f.warnings.length, 1);
    await assert.rejects(f.wait(), /No matching active/); f.clean();
  });
  await test('shutdown rejects and releases waiter resources', async () => {
    const f = fixture(); const result = f.wait(); const checked = assert.rejects(result, /stopped/);
    await tick(); f.extension.emit('shutdown'); await checked; f.clean();
  });
  await test('timeout rejects rather than treating delay as readiness', async () => {
    const f = fixture(); const result = f.wait(); const checked = assert.rejects(result, /Timed out/);
    await tick(); assert.equal(f.timers.size, 1); [...f.timers.values()][0]();
    await checked; f.clean();
  });
  await test('replaced policy cannot satisfy an earlier extension waiter', async () => {
    const f = fixture(); const result = f.wait(); const checked = assert.rejects(result, /changed/);
    await tick(); f.policies.set(f.extension.id, { extension: {} }); f.register();
    await checked; f.clean();
  });
  await test('version change during wait rejects', async () => {
    const f = fixture(); const result = f.wait(); const checked = assert.rejects(result, /changed/);
    await tick(); f.addon.version = '1.75.0'; f.register(); await checked; f.clean();
  });
  // Every launch after the first: the embedder holds all windows until this
  // wait resolves, so Gecko's own start trigger (first paint) never arrives.
  await test('delayed app-startup background is started rather than awaited forever', async () => {
    const f = fixture(); const started = f.primeDelayedBackground();
    const result = f.wait(); await tick(); await tick();
    assert.equal(started.count, 1, 'delayed background was started');
    await result; f.clean();
    f.extension.emit('start-background-script'); assert.equal(started.count, 1);
  });
  await test('background already starting or running is not started again', async () => {
    for (const state of ['starting', 'running']) {
      const f = fixture(); const started = f.primeDelayedBackground();
      f.extension.backgroundState = state;
      let settled = false; const result = f.wait().then(() => { settled = true; });
      await tick(); await tick();
      assert.equal(started.count, 0); assert.equal(settled, false);
      f.register(); await result; f.clean();
    }
  });
  await test('wait during extension startup judges the settled policy then starts its background', async () => {
    const f = fixture({ permission: false }); let settle;
    f.policies.set(f.extension.id, { extension: f.extension, readyPromise: new Promise(resolve => { settle = resolve; }) });
    let outcome; const result = f.wait().then(() => { outcome = 'resolved'; }, error => { outcome = error; });
    await tick(); await tick();
    assert.equal(outcome, undefined, 'judged before Extension.startup() loaded permissions');
    // Extension.startup(): the real policy replaces the temporary one.
    const real = { extension: f.extension }; f.policies.set(f.extension.id, real); f.grant(true); settle(real);
    await tick(); await tick(); assert.equal(outcome, undefined);
    // runManifest(): primeBackground(), then "ready".
    const started = f.primeDelayedBackground();
    await tick(); assert.equal(started.count, 0, 'started before its handler existed');
    f.extension.emit('ready'); await result;
    assert.equal(outcome, 'resolved'); assert.equal(started.count, 1); f.clean();
  });
  await test('interrupted extension startup rejects', async () => {
    const f = fixture(); let settle;
    f.policies.set(f.extension.id, { extension: f.extension, readyPromise: new Promise(resolve => { settle = resolve; }) });
    const checked = assert.rejects(f.wait(), /No matching active/);
    await tick(); f.policies.delete(f.extension.id); settle(null); await checked; f.clean();
  });
  await test('cancel during extension startup cannot later start a background or attach listeners', async () => {
    const f = fixture(); let settle;
    f.policies.set(f.extension.id, { extension: f.extension, readyPromise: new Promise(resolve => { settle = resolve; }) });
    const result = f.wait('1.74.0', requestA); const checked = assert.rejects(result, /cancelled/);
    await tick(); assert.equal(f.cancel(requestA), true); await checked; f.clean();
    const started = f.primeDelayedBackground();
    const real = { extension: f.extension }; f.policies.set(f.extension.id, real); settle(real);
    await tick(); await tick(); f.extension.emit('ready'); await tick();
    assert.equal(started.count, 0); f.clean();
  });
  await test('wait settled before ready does not start a background afterwards', async () => {
    const f = fixture(); const result = f.wait(); await tick();
    assert.equal(f.extension.listenerCount('ready'), 1);
    f.register(); await result; f.clean();
    const started = f.primeDelayedBackground(); f.extension.emit('ready'); await tick();
    assert.equal(started.count, 0);
  });
  process.stdout.write(`${passed} readiness lifecycle tests passed\n`);
  process.exitCode = 0;
})().catch(error => { console.error(error); process.exitCode = 1; });
