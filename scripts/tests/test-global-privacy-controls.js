/* Host tests execute the actual privileged module with explicit preference/I/O doubles.
 * They do not prove Gecko native persistence, document behavior or Android runtime. */
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const NAMES = {
  rfp: 'privacy.resistFingerprinting', webglPrompt: 'librewolf.webgl.prompt',
  webglHide: 'librewolf.webgl.prompt.hide', disableIPv6: 'network.dns.disableIPv6',
  referrerPolicy: 'network.http.referer.XOriginPolicy',
};
class Prefs {
  constructor() {
    this.defaults = new Map(Object.entries(NAMES).map(([id, name]) => [name, id === 'referrerPolicy' ? 1 : id !== 'disableIPv6']));
    this.user = new Map(); this.locks = new Set(); this.saved = new Map();
    this.saves = 0; this.writes = 0; this.beforeSave = async () => {}; this.afterWrite = () => {};
    this.permissions = new Map([['https://a.example:443', 'allow'], ['https://b.example:8443', 'deny']]);
  }
  effective(name) { return this.locks.has(name) ? this.defaults.get(name) : this.user.has(name) ? this.user.get(name) : this.defaults.get(name); }
  getPrefType(name) { const v = this.effective(name); return typeof v === 'boolean' ? 128 : Number.isInteger(v) ? 64 : typeof v === 'string' ? 32 : 0; }
  prefHasUserValue(name) { return this.user.has(name); }
  prefHasDefaultValue(name) { return this.defaults.has(name); }
  prefIsLocked(name) { return this.locks.has(name); }
  getDefaultBranch() { return { getBoolPref: n => this.typed(this.defaults.get(n), 'boolean'), getIntPref: n => this.typed(this.defaults.get(n), 'number') }; }
  typed(v, type) { if (typeof v !== type) throw Error('wrong type'); return v; }
  getBoolPref(name) { return this.typed(this.effective(name), 'boolean'); }
  getIntPref(name) { return this.typed(this.effective(name), 'number'); }
  getStringPref(name) { return this.typed(this.effective(name), 'string'); }
  setBoolPref(name, value) { this.set(name, value, 'boolean'); }
  setIntPref(name, value) { this.set(name, value, 'number'); }
  set(name, value, type) { if (this.locks.has(name)) throw Error('locked'); this.typed(value, type); if (this.defaults.get(name) === value) this.user.delete(name); else this.user.set(name, value); this.writes++; this.afterWrite(name); }
  clearUserPref(name) { if (this.locks.has(name)) throw Error('locked'); this.user.delete(name); this.writes++; this.afterWrite(name); }
  async savePrefFileAsync() { const snapshot = new Map(this.user); const call = ++this.saves; await this.beforeSave(call, snapshot); this.saved = snapshot; }
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const tests = [];
const test = (name, run) => tests.push({ name, run });
let Module;
const make = () => { const prefs = new Prefs(); return { prefs, settings: new Module.GlobalPrivacySettings(prefs) }; };
const pref = (state, id) => state.settings.find(v => v.id === id);
const set = (settings, id, value) => settings.request({ action: 'set', id, value });

test('native defaults and existing middle referrer choice are read without writes', async () => {
  const { prefs, settings } = make(); const state = await settings.request({ action: 'get' });
  assert.equal(pref(state, 'rfp').value, 1); assert.equal(pref(state, 'referrerPolicy').value, 1);
  assert.equal(pref(state, 'rfp').hasUser, false); assert.equal(prefs.saves, 0); assert.equal(prefs.writes, 0);
});
test('locked hidden user state is not confused with effective default', async () => {
  const { prefs, settings } = make(); prefs.user.set(NAMES.rfp, false); prefs.locks.add(NAMES.rfp);
  const state = pref(await settings.request({ action: 'get' }), 'rfp');
  assert.equal(state.value, 1); assert.equal(state.defaultValue, 1); assert.equal(state.hasUser, true);
  assert.equal(state.userValue, null); assert.equal(state.userValueKnown, false); assert.equal(state.locked, true);
});
test('unknown malformed mixed-batch and invalid typed writes reject before save or mutation', async () => {
  const { prefs, settings } = make();
  const bad = [null, [], [{ action: 'set', id: 'rfp', value: false }, { action: 'set', id: 'unknown', value: true }],
    { action: 'set', id: 'webgl.disabled', value: true }, { action: 'set', id: 'rfp', value: 0 },
    { action: 'set', id: 'referrerPolicy', value: true }, { action: 'set', id: 'referrerPolicy', value: 3 },
    { action: 'set', id: 'referrerPolicy', value: -1 }, { action: 'set', id: 'referrerPolicy', value: 1.5 },
    { action: 'set', id: 'referrerPolicy', value: '1' }, { action: 'reset', id: 'rfp', value: false },
    Object.assign([], { action: 'get' }), { action: 'get', id: 'rfp' }];
  for (const request of bad) assert.equal((await settings.request(request)).status, 'rejected');
  assert.equal(prefs.saves, 0); assert.equal(prefs.writes, 0);
});
test('locked requests and absent native pref types never touch persistence', async () => {
  const { prefs, settings } = make(); prefs.locks.add(NAMES.rfp);
  assert.equal((await set(settings, 'rfp', false)).reason, 'locked');
  prefs.defaults.delete(NAMES.webglHide);
  assert.equal((await set(settings, 'webglHide', false)).reason, 'unavailable');
  assert.equal(prefs.saves, 0); assert.equal(prefs.writes, 0);
});
test('preflight failure leaves this operation without any pref mutation', async () => {
  const { prefs, settings } = make(); prefs.beforeSave = async () => { throw Error('no profile'); };
  const result = await set(settings, 'rfp', false);
  assert.equal(result.reason, 'preflight-save-failed'); assert.equal(result.status, 'rejected');
  assert.equal(prefs.writes, 0); assert.equal(pref(result.state, 'rfp').hasUser, false);
});
test('lock changes during preflight are revalidated before mutation', async () => {
  const { prefs, settings } = make(); prefs.beforeSave = async () => { prefs.locks.add(NAMES.rfp); };
  assert.equal((await set(settings, 'rfp', false)).reason, 'locked'); assert.equal(prefs.writes, 0);
});
test('type changes during preflight are revalidated before mutation', async () => {
  const { prefs, settings } = make(); prefs.beforeSave = async () => { prefs.defaults.set(NAMES.rfp, 'unexpected'); };
  assert.equal((await set(settings, 'rfp', false)).reason, 'unavailable'); assert.equal(prefs.writes, 0);
});
test('native same-default normalization saves successfully and reset clears non-default choice', async () => {
  const { prefs, settings } = make(); const chosen = await set(settings, 'rfp', true);
  assert.equal(chosen.status, 'saved'); assert.equal(pref(chosen.state, 'rfp').hasUser, false);
  assert.equal(prefs.saved.has(NAMES.rfp), false);
  const custom = await set(settings, 'rfp', false); assert.equal(pref(custom.state, 'rfp').hasUser, true);
  const reset = await settings.request({ action: 'reset', id: 'rfp' });
  assert.equal(reset.status, 'saved'); assert.equal(pref(reset.state, 'rfp').value, 1);
  assert.equal(pref(reset.state, 'rfp').hasUser, false); assert.equal(prefs.saved.has(NAMES.rfp), false); assert.equal(prefs.saves, 6);
});
test('failed final save preserves actual memory and uncertainty across later read', async () => {
  const { prefs, settings } = make(); prefs.beforeSave = async call => { if (call === 2) throw Error('disk'); };
  const result = await set(settings, 'rfp', false);
  assert.equal(result.status, 'unconfirmed'); assert.equal(prefs.user.get(NAMES.rfp), false);
  assert.equal(prefs.saved.has(NAMES.rfp), false); const state = await settings.request({ action: 'get' });
  assert.equal(pref(state, 'rfp').value, 0); assert.equal(pref(state, 'rfp').persistenceUnconfirmed, true); assert.equal(prefs.saves, 2);
});
test('same-choice retry performs actual saves and clears prior uncertainty', async () => {
  const { prefs, settings } = make(); prefs.beforeSave = async call => { if (call === 2) throw Error('disk'); };
  await set(settings, 'rfp', false); const result = await set(settings, 'rfp', false);
  assert.equal(result.status, 'saved'); assert.equal(pref(result.state, 'rfp').persistenceUnconfirmed, false);
  assert.equal(prefs.saved.get(NAMES.rfp), false); assert.equal(prefs.saves, 4);
});
test('queued reads and reset wait until final I/O of the preceding change finishes', async () => {
  const { prefs, settings } = make(); const entered = deferred(); const release = deferred();
  prefs.beforeSave = async call => { if (call === 2) { entered.resolve(); await release.promise; } };
  const change = set(settings, 'rfp', false); await entered.promise;
  let readFinished = false; const read = settings.request({ action: 'get' }).then(v => { readFinished = true; return v; });
  const reset = settings.request({ action: 'reset', id: 'rfp' }); await Promise.resolve();
  assert.equal(readFinished, false); assert.equal(prefs.writes, 1); release.resolve();
  assert.equal((await change).status, 'saved'); assert.equal(pref(await read, 'rfp').value, 0);
  assert.equal((await reset).status, 'saved'); assert.equal(prefs.user.has(NAMES.rfp), false);
});
test('external write while final snapshot saves is superseded and current disk state unconfirmed', async () => {
  const { prefs, settings } = make(); prefs.beforeSave = async call => { if (call === 2) prefs.user.set(NAMES.rfp, true); };
  const result = await set(settings, 'rfp', false);
  assert.equal(result.status, 'superseded'); assert.equal(pref(result.state, 'rfp').value, 1);
  assert.equal(pref(result.state, 'rfp').persistenceUnconfirmed, true); assert.equal(prefs.saved.get(NAMES.rfp), false);
});
test('synchronous observer supersession cannot acknowledge the requested choice', async () => {
  const { prefs, settings } = make(); prefs.afterWrite = name => { prefs.user.set(name, true); };
  const result = await set(settings, 'rfp', false);
  assert.equal(result.status, 'superseded'); assert.equal(pref(result.state, 'rfp').value, 1);
});
test('setter throwing after mutation reports memory truth and unconfirmed save', async () => {
  const { prefs, settings } = make(); prefs.afterWrite = () => { throw Error('observer'); };
  const result = await set(settings, 'rfp', false);
  assert.equal(result.reason, 'write-failed'); assert.equal(pref(result.state, 'rfp').value, 0);
  assert.equal(pref(result.state, 'rfp').persistenceUnconfirmed, true); assert.equal(prefs.saves, 1);
});
test('queued request captures caller choice before caller mutation', async () => {
  const { settings } = make(); const request = { action: 'set', id: 'rfp', value: false };
  const operation = settings.request(request); request.value = true; request.id = 'webglPrompt';
  const result = await operation; assert.equal(pref(result.state, 'rfp').value, 0); assert.equal(pref(result.state, 'webglPrompt').hasUser, false);
});
test('a failed read cannot poison later serialized operations', async () => {
  const { prefs, settings } = make(); const original = prefs.getBoolPref.bind(prefs);
  prefs.getBoolPref = () => { throw Error('read failure'); };
  await assert.rejects(settings.request({ action: 'get' })); prefs.getBoolPref = original;
  assert.equal((await set(settings, 'rfp', false)).status, 'saved');
});
test('unknown existing referrer integer is preserved by read but not admitted as a write', async () => {
  const { prefs, settings } = make(); prefs.user.set(NAMES.referrerPolicy, 99);
  assert.equal(pref(await settings.request({ action: 'get' }), 'referrerPolicy').value, 99);
  assert.equal((await set(settings, 'referrerPolicy', 99)).status, 'rejected'); assert.equal(prefs.writes, 0);
});
test('global WebGL mode and quiet flag leave exact site decisions intact', async () => {
  const { prefs, settings } = make(); const prior = [...prefs.permissions];
  await set(settings, 'webglPrompt', false); await set(settings, 'webglHide', false);
  await settings.request({ action: 'reset', id: 'webglPrompt' }); assert.deepEqual([...prefs.permissions], prior);
});
(async () => {
  global.Ci = { nsIPrefBranch: { PREF_BOOL: 128, PREF_INT: 64 } }; global.Services = { prefs: new Prefs() };
  Module = await import(pathToFileURL(process.argv[2]));
  for (const { name, run } of tests) { await run(); console.log('PASS ' + name); }
  console.log(`PASS ${tests.length} actual-module host tests with explicit pref/I/O doubles; native/Android execution NOT RUN`);
})().catch(error => { console.error(error); process.exitCode = 1; });
