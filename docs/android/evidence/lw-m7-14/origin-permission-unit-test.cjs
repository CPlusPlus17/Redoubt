/* Execute the actual patched GeckoView modules with minimal platform doubles.
 * Usage: node origin-permission-unit-test.cjs /path/to/patched/gecko/source
 * This proves bridge logic; it does not replace native/instrumentation tests. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const root = process.argv[2];
if (!root) throw new Error('Pass the patched Gecko source directory');
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
const principal = (origin = 'https://frame.example:8443', pb = 0, context = '') => ({
  originNoSuffix: origin, origin: origin + (pb || context ? `^privateBrowsingId=${pb}&geckoViewSessionContextId=${context}` : ''),
  originAttributes: { privateBrowsingId: pb, geckoViewSessionContextId: context },
  privateBrowsingId: pb, URI: { scheme: origin.split(':')[0] }, isContentPrincipal: true,
  equals(other) { return this.origin === other?.origin; },
});
function fixture() {
  const rows = new Map(), writes = [], events = [], errors = [];
  let serial = 0;
  const key = (p, type) => `${p.origin}|${type}`;
  const perms = {
    ALLOW_ACTION: 1, DENY_ACTION: 2, PROMPT_ACTION: 3, EXPIRE_NEVER: 0, EXPIRE_SESSION: 2,
    getPermissionObject(p, type, exact) { assert.equal(exact, true); return rows.get(key(p, type)); },
    addFromPrincipal(p, type, value, expireType) { writes.push({ p, type, value, expireType }); rows.set(key(p, type), { principal: p, type, capability: value, expireType, modificationTime: ++serial }); },
    removeFromPrincipal(p, type) { rows.delete(key(p, type)); },
    get all() { return [...rows.values()]; },
    getAllForPrincipal(p) { return [...rows.values()].filter(row => row.principal.equals(p)); },
  };
  const Services = { perms, uuid: { generateUUID: () => `{request-${++serial}}` },
    io: { createExposableURI: uri => uri },
  };
  let permissionService;
  const GeckoViewUtils = { initLogging: () => ({ debug() {}, warn() {} }) };
  class ActorBase { static initLogging() { return GeckoViewUtils.initLogging(); } receiveMessage() {} }
  const context = vm.createContext({
    Components: { ID: value => value },
    console: { error: (...args) => errors.push(args) }, Services, Map, Set, Promise,
    GeckoViewUtils, GeckoViewActorParent: ActorBase, GeckoViewActorChild: ActorBase,
    ChromeUtils: { generateQI: () => function() {}, defineESModuleGetters(lazy) { Object.assign(lazy, {
      E10SUtils: { serializePrincipal: p => p, deserializePrincipal: p => p },
      EventDispatcher: { instance: { registerListener() {} } },
    }); } },
    XPCOMUtils: { defineLazyPreferenceGetter() {} },
    Ci: new Proxy({}, { get: () => new Proxy({}, { get: () => 0 }) }),
    Cc: new Proxy({}, { get: () => ({ getService: () => ({ wrappedJSObject: permissionService }) }) }),
  });
  function load(relative, name) {
    let source = fs.readFileSync(path.join(root, relative), 'utf8');
    source = source.replace(/^import .*;\n/gm, '').replace(/export (class|const) /g, '$1 ');
    return vm.runInContext(`(() => { ${source}\nreturn ${name}; })()`, context, { filename: relative });
  }
  const Permission = load('mobile/shared/components/geckoview/GeckoViewPermission.sys.mjs', 'GeckoViewPermission');
  permissionService = new Permission();
  const Storage = load('mobile/shared/modules/geckoview/GeckoViewStorageController.sys.mjs', 'GeckoViewStorageController');
  const Parent = load('mobile/shared/actors/GeckoViewPermissionParent.sys.mjs', 'GeckoViewPermissionParent');
  const Child = load('mobile/shared/actors/GeckoViewPermissionChild.sys.mjs', 'GeckoViewPermissionChild');
  function actor(p = principal()) {
    const answer = deferred(), result = new Parent();
    result.manager = { documentPrincipal: p, isCurrentGlobal: true, isActiveInTab: true };
    result.browser = {};
    result.browsingContext = { currentWindowGlobal: result.manager, top: { currentWindowGlobal: { documentPrincipal: principal('https://top.example') } },
      reload() { result.reloads = (result.reloads || 0) + 1; } };
    result.eventDispatcher = { sendRequestForResult(name, data) { events.push({ name, data }); return answer.promise; } };
    return { actor: result, answer };
  }
  const update = data => {
    const snapshot = perms.getPermissionObject(data.principal, data.perm, true);
    const input = { value: snapshot?.capability, expireType: snapshot?.expireType, modificationTime: snapshot?.modificationTime, ...data };
    return new Promise((resolve, reject) => Storage.onEvent('GeckoView:SetOriginPermission', input, { onSuccess: resolve, onError: message => reject(new Error(message)) }));
  };
  return { service: permissionService, perms, writes, rows, events, errors, actor, Child, update, Storage };
}
const decision = (value = 1, permanent = false) => ({ value, permanent });
test('request uses actor frame principal, quiet metadata, and exact session lifetime', async () => {
  const f = fixture(), p = principal(), { actor, answer } = f.actor(p);
  const result = f.service.requestOriginPermission(actor, 'canvas', true);
  const data = f.events[0].data;
  assert.equal(data.principal, p); assert.equal(data.uri, p.originNoSuffix);
  assert.equal(data.topLevelOrigin, 'https://top.example'); assert.equal(data.isQuiet, true);
  assert.equal(data.principalOrigin, p.origin); assert.equal(data.expireType, 2);
  answer.resolve(decision()); assert.equal(await result, true);
  assert.equal(await f.service.awaitOriginPermissionDecision(data.requestId), true);
  assert.equal(f.writes[0].p, p); assert.equal(f.writes[0].expireType, 2);
});
for (const value of [1, 2]) for (const permanent of [false, true]) for (const pb of [0, 1]) {
  test(`decision ${value}, permanent=${permanent}, private=${pb} writes correct lifetime`, async () => {
    const f = fixture(), { actor, answer } = f.actor(principal(undefined, pb, 'container'));
    const result = f.service.requestOriginPermission(actor, 'webgl', false);
    answer.resolve(decision(value, permanent)); assert.equal(await result, true);
    assert.equal(f.writes[0].value, value);
    assert.equal(f.writes[0].expireType, permanent && !pb ? 0 : 2);
    assert.equal(f.events[0].data.contextId, 'container');
  });
}
test('dismissal neither writes nor erases an existing exception', async () => {
  const f = fixture(), p = principal(), { actor, answer } = f.actor(p);
  f.perms.addFromPrincipal(p, 'canvas', 2, 0);
  const result = f.service.requestOriginPermission(actor, 'canvas', true);
  answer.resolve(decision(3)); assert.equal(await result, false);
  assert.equal(f.writes.length, 1); assert.equal(f.perms.getPermissionObject(p, 'canvas', true).capability, 2);
  assert.equal(await f.service.awaitOriginPermissionDecision(f.events[0].data.requestId), false);
});
for (const bad of [false, null, { value: 1 }, { value: 4, permanent: false }, { value: '1', permanent: false }, { value: 1, permanent: 1 }]) {
  test(`invalid app decision ${JSON.stringify(bad)} cannot write`, async () => {
    const f = fixture(), { actor, answer } = f.actor();
    const result = f.service.requestOriginPermission(actor, 'canvas', false);
    answer.resolve(bad); assert.equal(await result, false); assert.equal(f.writes.length, 0);
  });
}
test('stale same-origin document reply cannot grant to its replacement', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = f.service.requestOriginPermission(actor, 'canvas', true);
  actor.browsingContext.currentWindowGlobal = { documentPrincipal: actor.manager.documentPrincipal };
  answer.resolve(decision()); assert.equal(await result, false); assert.equal(f.writes.length, 0);
});
test('changed actor principal cannot receive a captured decision', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = f.service.requestOriginPermission(actor, 'canvas', true);
  actor.manager.documentPrincipal = principal('https://other.example');
  answer.resolve(decision()); assert.equal(await result, false); assert.equal(f.writes.length, 0);
});
test('destroy cancels outstanding result and observer without waiting for app reply', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = f.service.requestOriginPermission(actor, 'canvas', true);
  const waiting = f.service.awaitOriginPermissionDecision(f.events[0].data.requestId);
  actor.didDestroy(); assert.equal(await waiting, false); assert.equal(await result, false);
  answer.resolve(decision()); await Promise.resolve(); assert.equal(f.writes.length, 0);
});
test('same-origin navigation after commit prevents stale acknowledgement and reload', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = f.service.requestOriginPermission(actor, 'webgl', false);
  answer.resolve(decision()); await result;
  actor.browsingContext.currentWindowGlobal = { documentPrincipal: actor.manager.documentPrincipal };
  const id = f.events[0].data.requestId;
  assert.equal(await f.service.awaitOriginPermissionDecision(id), false);
  assert.equal(await f.service.reloadOriginPermissionDocument(id), false); assert.equal(actor.reloads, undefined);
});
test('concurrent reloads only reload requesting frame once after write', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = f.service.requestOriginPermission(actor, 'webgl', false);
  const id = f.events[0].data.requestId;
  const one = f.service.reloadOriginPermissionDocument(id), two = f.service.reloadOriginPermissionDocument(id);
  assert.equal(actor.reloads, undefined); answer.resolve(decision()); await result;
  assert.deepEqual(await Promise.all([one, two]), [true, false]); assert.equal(actor.reloads, 1);
});
test('write failure rejects applied acknowledgement', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  f.perms.addFromPrincipal = () => { throw new Error('storage failure'); };
  const result = f.service.requestOriginPermission(actor, 'webgl', false);
  answer.resolve(decision()); assert.equal(await result, false);
  assert.equal(await f.service.awaitOriginPermissionDecision(f.events[0].data.requestId), false);
});
for (const origin of ['file:///tmp/test', 'moz-extension://uuid', 'resource://test']) {
  test(`non-web ${origin} cannot prompt`, async () => {
    const f = fixture(), { actor } = f.actor(principal(origin));
    assert.equal(await f.service.requestOriginPermission(actor, 'canvas', true), false); assert.equal(f.events.length, 0);
  });
}
test('opaque and stale actors, invalid kinds, and invalid quiet flags cannot prompt', async () => {
  const f = fixture(), { actor } = f.actor();
  actor.manager.documentPrincipal.isContentPrincipal = false;
  assert.equal(await f.service.requestOriginPermission(actor, 'canvas', true), false);
  assert.equal(await f.service.requestOriginPermission({}, 'canvas', true), false);
  assert.equal(await f.service.requestOriginPermission(actor, 'geolocation', true), false);
  assert.equal(await f.service.requestOriginPermission(actor, 'webgl', 'quiet'), false);
  assert.equal(f.events.length, 0);
});
test('parent deduplicates each kind for one actor and ignores forged origin data', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const message = { name: 'GeckoView:RequestCanvasPermission', data: { kind: 'canvas', quiet: true, principal: principal('https://forged.example') } };
  const result = actor.receiveMessage(message); assert.equal(actor.receiveMessage(message), null);
  assert.equal(f.events.length, 1); assert.equal(f.events[0].data.uri, 'https://frame.example:8443');
  answer.resolve(decision()); await result;
});
test('child accepts only its own inner window and emits no principal supplied by content', () => {
  const f = fixture(), child = new f.Child(), sent = [];
  child.contentWindow = {}; child.sendAsyncMessage = (...data) => sent.push(data);
  child.observe({}, 'geckoview-canvas-permission', 'quiet');
  child.observe(child.contentWindow, 'other', 'quiet');
  child.observe(child.contentWindow, 'geckoview-canvas-permission', 'invalid');
  assert.equal(sent.length, 0);
  child.observe(child.contentWindow, 'geckoview-canvas-permission', 'quiet');
  assert.equal(sent.length, 1); assert.equal(JSON.stringify(sent[0]), JSON.stringify(['GeckoView:RequestCanvasPermission', { kind: 'canvas', quiet: true }]));
});
test('exact revoke preserves scheme, port, subdomain, private, context, and other kind records', async () => {
  const f = fixture(), p = principal();
  const others = [principal('http://frame.example:8443'), principal('https://frame.example'), principal('https://sub.frame.example:8443'), principal(undefined, 1), principal(undefined, 0, 'other')];
  for (const item of [p, ...others]) f.perms.addFromPrincipal(item, 'canvas', 1, 2);
  f.perms.addFromPrincipal(p, 'webgl', 2, 0);
  await f.update({ principal: p, principalOrigin: p.origin, perm: 'canvas', newValue: 3, permanent: false });
  assert.equal(f.perms.getPermissionObject(p, 'canvas', true), undefined);
  for (const item of others) assert.equal(f.perms.getPermissionObject(item, 'canvas', true).capability, 1);
  assert.equal(f.perms.getPermissionObject(p, 'webgl', true).capability, 2);
});
test('stored updates validate exact principal identity and acknowledged lifetime', async () => {
  const f = fixture(), p = principal(undefined, 1);
  f.perms.addFromPrincipal(p, 'canvas', 2, 2);
  const data = { principal: p, principalOrigin: p.origin, perm: 'canvas', newValue: 1, permanent: true };
  await f.update(data); assert.equal(f.writes[1].expireType, 2);
  await assert.rejects(f.update({ ...data, principalOrigin: p.originNoSuffix }));
  await assert.rejects(f.update({ ...data, perm: 'camera' }));
  await assert.rejects(f.update({ ...data, newValue: '1' }));
  await assert.rejects(f.update({ ...data, permanent: undefined }));
  assert.equal(f.writes.length, 2);
});
test('record enumeration exports actual expiry and canonical origin with attributes', async () => {
  const f = fixture(), p = principal(undefined, 1, 'context');
  f.perms.addFromPrincipal(p, 'webgl', 1, 2);
  const result = await new Promise(resolve => f.Storage.onEvent('GeckoView:GetAllPermissions', {}, { onSuccess: resolve }));
  const row = result.permissions[0];
  assert.equal(row.uri, p.originNoSuffix); assert.equal(row.principalOrigin, p.origin); assert.equal(row.expireType, 2);
  assert.equal(row.privateMode, true); assert.equal(row.contextId, 'context');
});

for (const state of ['isCurrentGlobal', 'isActiveInTab']) {
  test(`inactive ancestor or BFCache window (${state}) cannot grant`, async () => {
    const f = fixture(), { actor, answer } = f.actor();
    const result = f.service.requestOriginPermission(actor, 'canvas', true);
    actor.manager[state] = false; answer.resolve(decision());
    assert.equal(await result, false); assert.equal(f.writes.length, 0);
  });
}

test('private-ended or revoked snapshot cannot recreate its record', async () => {
  const f = fixture(), p = principal(undefined, 1);
  f.perms.addFromPrincipal(p, 'canvas', 1, 2);
  const snapshot = f.perms.getPermissionObject(p, 'canvas', true);
  f.perms.removeFromPrincipal(p, 'canvas');
  await assert.rejects(f.update({ principal: p, principalOrigin: p.origin, perm: 'canvas', value: snapshot.capability, expireType: snapshot.expireType, modificationTime: snapshot.modificationTime, newValue: 2, permanent: false }));
  assert.equal(f.perms.getPermissionObject(p, 'canvas', true), undefined);
});
test('stale settings snapshot cannot overwrite a newer same-value lifetime record', async () => {
  const f = fixture(), p = principal();
  f.perms.addFromPrincipal(p, 'canvas', 1, 2);
  const old = f.perms.getPermissionObject(p, 'canvas', true);
  f.perms.addFromPrincipal(p, 'canvas', 1, 2);
  await assert.rejects(f.update({ principal: p, principalOrigin: p.origin, perm: 'canvas', value: old.capability, expireType: old.expireType, modificationTime: old.modificationTime, newValue: 2, permanent: false }));
  assert.equal(f.perms.getPermissionObject(p, 'canvas', true).capability, 1);
});
test('pending document decision cannot overwrite a newer origin choice', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = f.service.requestOriginPermission(actor, 'canvas', true);
  f.perms.addFromPrincipal(actor.manager.documentPrincipal, 'canvas', 2, 0);
  answer.resolve(decision()); assert.equal(await result, false); assert.equal(f.writes.length, 1);
});
test('trusted pagehide cancels quiet requests and permits a fresh request after restore', async () => {
  const f = fixture(), { actor, answer } = f.actor();
  const result = actor.receiveMessage({ name: 'GeckoView:RequestCanvasPermission', data: { kind: 'canvas', quiet: true } });
  const child = new f.Child(); child.sendAsyncMessage = name => actor.receiveMessage({ name });
  child.handleEvent({ type: 'pagehide', isTrusted: false });
  assert.equal(f.events.length, 1);
  child.handleEvent({ type: 'pagehide', isTrusted: true });
  assert.equal(await result, false);
  const again = actor.receiveMessage({ name: 'GeckoView:RequestCanvasPermission', data: { kind: 'canvas', quiet: true } });
  assert.equal(f.events.length, 2); answer.resolve(decision()); assert.equal(await again, true);
});
