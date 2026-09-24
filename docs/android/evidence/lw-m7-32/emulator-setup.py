#!/usr/bin/env python3
"""Scoped TLS fixture setup + cookie runner + cleanup on an existing AOSP emulator.

No emulator launch, APK install, profile wipe, policy-pref changes, certificate
error overrides, shared image edits, host DNS changes or private-key reads.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import re
import secrets
import socket
import shlex
import shutil
import ssl
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location('lw32_cookie', ROOT / 'scripts/android-cookie-banner-smoke.py')
cookie = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cookie)
g = cookie.g
Pending = g.Pending
NAMES = ('cookies.fixture.test', 'sub.cookies.fixture.test', 'duh.de')
HOSTS = '/system/etc/hosts'
SHA = re.compile(r'[0-9a-f]{64}')


def need(value, message):
    if not value:
        raise Pending(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def public_inputs(ca, manifest):
    raw, receipt = ca.read_bytes(), json.loads(manifest.read_text())
    need(len(raw) < 65536 and raw.count(b'-----BEGIN CERTIFICATE-----') == 1 and
         re.fullmatch(rb'\s*-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*', raw),
         'Expected exactly one public PEM certificate, never private material')
    der = ssl.PEM_cert_to_DER_cert(raw.decode('ascii'))
    need(receipt.get('dns_names') == list(NAMES), 'Unrecognized fixture hostname allowlist')
    need(sha(raw) == receipt.get('ca_pem_sha256') and sha(der) == receipt.get('ca_der_sha256'),
         'Public certificate differs from the retained fixture manifest')
    need(bool(SHA.fullmatch(receipt.get('server_pem_sha256', ''))), 'Missing retained server certificate hash')
    check = subprocess.run(['openssl', 'verify', '-check_ss_sig', '-CAfile', str(ca), str(ca)],
                           capture_output=True, text=True, timeout=15)
    need(check.returncode == 0, 'Public CA is invalid, expired, or not yet valid: ' + check.stderr.strip())
    return receipt, base64.b64encode(der).decode('ascii')


def emulator_identity(serial, props):
    need(bool(re.fullmatch(r'emulator-[0-9]+', serial)), 'Explicit emulator-NNNN serial required')
    need(props['qemu'] == '1' and props['debuggable'] == '1' and
         props['type'] in ('userdebug', 'eng'), 'Dedicated rootable AOSP emulator required')
    need(bool(re.fullmatch(r'[0-9a-f-]{36}', props['boot'])), 'Cannot bind setup to an emulator boot')
    need('generic' in props['fingerprint'] or 'aosp' in props['fingerprint'],
         'AOSP image identity could not be established')


def hosts_body(original):
    need(len(original.encode()) < 65536, 'Unexpectedly large hosts file')
    for line in original.splitlines():
        fields = line.split('#', 1)[0].split()
        need(not set(name.lower() for name in fields[1:]).intersection(NAMES),
             'Controlled hosts already have a mapping; preserve it and use a fresh emulator')
    return original.rstrip('\n') + '\n' + ''.join('127.0.0.1 ' + name + '\n' for name in NAMES)


def mount_entries(body):
    entries = []
    for line in body.splitlines():
        fields = line.split()
        if len(fields) >= 10 and fields[4] == HOSTS:
            entries.append(fields)
    return entries


def owns_mount(entries, source_stat, target_stat, source_hash, target_hash, expected_hash):
    return (len(entries) == 1 and bool(re.fullmatch(r'[0-9]+:[0-9]+', source_stat)) and
            source_stat == target_stat and source_hash == target_hash == expected_hash)


def validate_profile(package, profile):
    need(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+', package)), 'Invalid package')
    need(profile.startswith((f'/data/user/0/{package}/', f'/data/data/{package}/')) and
         '..' not in Path(profile).parts and not any(c.isspace() for c in profile),
         'Expected profile must be an exact absolute path in the selected package')


def validate_journal(state):
    need(state.get('version') == 1 and bool(re.fullmatch(r'[0-9a-f]{24}',state.get('run',''))),
         'Invalid setup journal identity')
    validate_profile(state.get('package',''),state.get('profile',''))
    need(bool(SHA.fullmatch(state.get('caSha256',''))) and
         sha(base64.b64decode(state.get('caBase64',''),validate=True)) == state['caSha256'],
         'Journal public certificate hash differs')
    if 'remoteDir' in state:
        need(state['remoteDir'] == '/data/local/tmp/lw-cookie-' + state['run'], 'Invalid journal remote directory')
    else:
        need(not state.get('owned',{}).get('remoteDir') and not state.get('owned',{}).get('hostsMount'),
             'Missing journal remote directory')
    if 'configPath' in state:
        need(state['configPath'] == f"/data/local/tmp/{state['package']}-geckoview-config.yaml", 'Invalid journal config path')
    if 'forwardPort' in state:
        need(type(state['forwardPort']) is int and 1 <= state['forwardPort'] <= 65535, 'Invalid journal forward port')
    keys = {'cert','config','debugApp','hostsMount','remoteDir','httpsReverse','bootstrapReverse','forward','adbdRoot'}
    need(isinstance(state.get('owned'),dict) and set(state['owned']) <= keys and
         all(type(value) is bool for value in state['owned'].values()), 'Invalid journal ownership flags')


CERT_JS = r"""
const [action, expectedProfile, fingerprint, encoded, expectedKey] = arguments;
const profile = Services.dirsvc.get('ProfD', Ci.nsIFile).path;
if (profile !== expectedProfile) throw new Error('Unexpected Gecko profile: ' + profile);
const db = Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB);
const digest = cert => cert.sha256Fingerprint.replaceAll(':','').toLowerCase();
const trusted = cert => db.isCertTrusted(cert, Ci.nsIX509Cert.CA_CERT, Ci.nsIX509CertDB.TRUSTED_SSL);
let matches = db.getCerts().filter(cert => digest(cert) === fingerprint);
if (matches.length > 1) throw new Error('Ambiguous fixture certificate identity');
if (action === 'import') {
  if (matches.length) throw new Error('Fixture CA already exists; it is not ours to modify');
  if (Services.cookies.getCookiesWithOriginAttributes('{}').length)
    throw new Error('Expected a fresh dedicated profile with no cookies');
  const decoded = db.constructX509FromBase64(encoded);
  if (digest(decoded) !== fingerprint) throw new Error('DER fingerprint mismatch');
  const added = db.addCertFromBase64(encoded, 'C,,');
  if (digest(added) !== fingerprint || !trusted(added)) throw new Error('Import/trust did not match');
  return {profile, sha256:digest(added), dbKey:added.dbKey, trusted:true, cookiesBefore:0};
}
if (action === 'remove' && matches.length) {
  if (expectedKey && matches[0].dbKey !== expectedKey) throw new Error('Certificate DB key changed');
  db.deleteCertificate(matches[0]);
}
matches = db.getCerts().filter(cert => digest(cert) === fingerprint);
return {profile, sha256:fingerprint, matches:matches.length,
  dbKey:matches[0]?.dbKey || null, trusted:matches.some(trusted)};
"""
DNS_JS = r"""
return Promise.all(arguments[0].map(name => new Promise(resolve => {
  const listener = {onLookupComplete(_request, record, status) {
    const addresses = [];
    if (Components.isSuccessCode(status)) {
      record = record.QueryInterface(Ci.nsIDNSAddrRecord);
      while (record.hasMore()) addresses.push(record.getNextAddrAsString());
    }
    resolve({name, status, addresses});
  }, QueryInterface:ChromeUtils.generateQI(['nsIDNSListener'])};
  Services.dns.asyncResolve(name, Ci.nsIDNSService.RESOLVE_TYPE_DEFAULT,
    Ci.nsIDNSService.RESOLVE_BYPASS_CACHE, null, listener, Services.tm.currentThread, {});
})));
"""


def grade_dns(rows):
    need(isinstance(rows, list) and len(rows) == len(NAMES) and
         {row.get('name') for row in rows} == set(NAMES), 'Missing or duplicate Gecko DNS observations')
    for row in rows:
        need(row.get('status') == 0 and row.get('addresses') and
             set(row['addresses']) == {'127.0.0.1'},
             'Gecko did not resolve exclusively to the controlled loopback: ' + row['name'])
    return rows


class Setup:
    def __init__(self, args, state=None):
        self.args = args
        self.protocol = g.foundation()
        self.adb = self.protocol.Adb(args.adb, args.serial)
        self.state = state or {'version': 1, 'run': secrets.token_hex(12), 'status': 'PENDING',
                              'owned': {}, 'events': [], 'acceptanceComplete': False}
        self.client = self.server = None
        self.work = args.work.resolve()
        self.journal = self.work / 'setup.json'

    def save(self):
        temporary = self.journal.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(self.journal)

    def event(self, name, detail=None):
        self.state['events'].append({'time': time.time(), 'name': name, 'detail': detail})
        self.save()

    def shell(self, *args, check=True):
        result = self.adb.run('shell', shlex.join(args), timeout=30, check=check)
        return result.stdout.strip()

    def mark(self, step):
        self.state['owned'][step] = True
        self.save()  # Write intent before the external mutation, for interrupted recovery.

    def identify(self):
        props = {name: self.shell('getprop', key) for name, key in (
            ('qemu','ro.kernel.qemu'), ('debuggable','ro.debuggable'), ('type','ro.build.type'),
            ('fingerprint','ro.build.fingerprint'))}
        props['boot'] = self.shell('cat', '/proc/sys/kernel/random/boot_id')
        emulator_identity(self.args.serial, props)
        return props

    def bind_identity(self):
        current = self.identify()
        if 'identity' in self.state:
            need(current == self.state['identity'], 'Emulator boot/image changed; refusing cleanup on another instance')
        else:
            self.state['identity'] = current
            self.state['serial'] = self.args.serial
        return current

    def installed(self):
        paths = [line[8:] for line in self.shell('pm','path',self.args.package).splitlines()
                 if line.startswith('package:')]
        need(paths, 'Installed APK is absent; helper never installs')
        flags = [line.strip() for line in self.shell('dumpsys','package',self.args.package).splitlines()
                 if re.match(r'\s*(pkgFlags|flags|privateFlags)=', line)]
        need(flags and not any('DEBUGGABLE' in line for line in flags), 'Expected release-type non-debuggable APK')
        hashes = [{'path': path, 'sha256': self.shell('sha256sum', path).split()[0]} for path in paths]
        need(any(row['sha256'] == self.state['apkSha256'] for row in hashes), 'Wrong installed APK')
        self.event('installed-apk', {'files': hashes, 'flags': flags})

    def create_reverse(self, key, local, remote):
        rows = [row.split() for row in self.adb.run('reverse','--list',check=True,timeout=30).stdout.splitlines()]
        matches = [row for row in rows if len(row) == 3 and row[1] == local]
        if matches:
            need(self.state['owned'].get(key) and len(matches) == 1 and matches[0][2] == remote,
                 'Existing reverse route is not owned by this setup')
            return
        self.mark(key)
        self.adb.run('reverse','--no-rebind',local,remote,check=True,timeout=30)

    def bootstrap(self):
        if self.server:
            return
        proof = secrets.token_hex(32)
        route = '/__lw32/' + secrets.token_hex(16)
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                if self.path != route:
                    self.send_error(404); return
                body = json.dumps({'proof': proof}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers(); self.wfile.write(body)
        class Server(http.server.ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True
        self.server = Server(('127.0.0.1', 48761), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.proof, self.route = proof, route
        self.create_reverse('bootstrapReverse','tcp:48761','tcp:48761')

    def stop_bootstrap(self):
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.server = None
        if self.state['owned'].get('bootstrapReverse'):
            self.remove_route('reverse', 'tcp:48761', 'tcp:48761')
            self.state['owned']['bootstrapReverse'] = False
            self.save()

    def remove_route(self, kind, local, remote):
        rows = self.adb.run(kind,'--list',check=True,timeout=30).stdout.splitlines()
        matches = [row.split() for row in rows if len(row.split()) == 3 and row.split()[1] == local]
        if matches:
            need(len(matches) == 1 and matches[0][2] == remote, 'ADB route was replaced; preserve external state')
            if kind == 'forward':
                need(matches[0][0] == self.args.serial, 'Forward belongs to another device')
            self.adb.run(kind,'--remove',local,check=True,timeout=30)

    def create_forward(self):
        local = f"tcp:{self.state['forwardPort']}"
        rows = [row.split() for row in self.adb.run('forward','--list',check=True,timeout=30).stdout.splitlines()]
        matches = [row for row in rows if len(row) == 3 and row[1] == local]
        if matches:
            need(self.state['owned'].get('forward') and matches == [[self.args.serial, local, 'tcp:2828']],
                 'Marionette forward belongs to another owner')
            return
        self.mark('forward')
        self.adb.run('forward','--no-rebind',local,'tcp:2828',check=True,timeout=30)

    def connect(self, restart=False):
        self.create_forward()
        if self.client:
            self.client.close(); self.client = None
        if restart:
            self.shell('am','force-stop',self.args.package)
        self.bootstrap()
        self.state['appStarted'] = True; self.save()
        self.shell('am','start','-a','android.intent.action.VIEW','-d',
                   'http://localhost:48761' + self.route,'-p',self.args.package)
        deadline = time.monotonic() + 60
        last = ''
        while time.monotonic() < deadline:
            client = None
            try:
                client = self.protocol.Marionette(self.state['forwardPort'], timeout=20)
                client.cmd('WebDriver:NewSession', {'capabilities': {'alwaysMatch': {}}})
                client.cmd('WebDriver:SetTimeouts', {'script': 20000, 'pageLoad': 60000})
                self.client = client
                return
            except Exception as error:
                last = str(error)
                if client:
                    client.close()
                time.sleep(0.5)
        raise Pending('Marionette unavailable after loopback bootstrap: ' + last)

    def cert(self, action):
        return self.client.script(CERT_JS, [action, self.args.expected_profile,
            self.state['caSha256'], self.state['caBase64'] if action == 'import' else '',
            self.state.get('cert', {}).get('dbKey')], chrome=True)

    def prepare(self, receipt, encoded):
        self.state.update({'package': self.args.package, 'profile': self.args.expected_profile,
                          'apkSha256': sha(self.args.apk.read_bytes()), 'caSha256': receipt['ca_der_sha256'],
                          'caBase64': encoded, 'fixtureManifest': receipt,
                          'freshDedicatedProfile': 'explicit operator declaration; zero cookies checked before import',
                          'protocolSha256': self.protocol.input_sha256})
        self.bind_identity(); self.installed()
        self.state['initialUid'] = self.shell('id','-u')
        if self.state['initialUid'] != '0':
            need(not self.adb.run('reverse','--list',check=True,timeout=30).stdout.strip() and
                 not any(row.split()[0] == self.args.serial for row in
                         self.adb.run('forward','--list',check=True,timeout=30).stdout.splitlines() if row.split()),
                 'adb root would disturb existing device routes; require an already-rooted dedicated emulator')
            self.mark('adbdRoot')
            self.adb.run('root',check=True,timeout=30)
            self.adb.run('wait-for-device',check=True,timeout=30)
            self.bind_identity()
        need(self.shell('id','-u') == '0', 'adb root is unavailable; no remount fallback')
        need(not mount_entries(self.shell('cat','/proc/self/mountinfo')), 'Hosts already has a file mount')
        original = self.adb.run('exec-out','cat',HOSTS,check=True,timeout=30).stdout
        original_sha = self.shell('sha256sum',HOSTS).split()[0]
        need(sha(original.encode()) == original_sha, 'Cannot preserve original hosts bytes exactly')
        body = hosts_body(original)
        self.state.update({'originalHostsSha256': original_sha, 'hostsSha256': sha(body.encode()),
                           'remoteDir': '/data/local/tmp/lw-cookie-' + self.state['run']})
        remote = self.state['remoteDir']
        need(self.adb.run('shell',shlex.join(['test','-e',remote]),timeout=30).returncode == 1,
             'Setup directory already exists or cannot be inspected')
        self.mark('remoteDir'); self.shell('mkdir',remote)
        local = self.work / 'hosts'; local.write_text(body)
        self.adb.run('push',str(local),remote+'/hosts',check=True,timeout=30)
        self.shell('chmod','644',remote+'/hosts')
        label = self.shell('ls','-Z',HOSTS).split()[0]
        need(bool(re.fullmatch(r'u:object_r:[a-z0-9_]+:s0',label)), 'Cannot preserve hosts SELinux label')
        self.shell('chcon',label,remote+'/hosts')
        self.mark('hostsMount'); self.shell('mount','--bind',remote+'/hosts',HOSTS)
        need(self.mount_owned(), 'Bind mount identity could not be verified')
        self.create_reverse('httpsReverse','tcp:443','tcp:48762')
        config = 'args:\n  - "-remote-allow-system-access"\nenv:\n  MOZ_MARIONETTE: "1"\nprefs:\n  remote.prefs.recommended: false\n  marionette.port: 2828\n'
        self.state['configPath'] = f'/data/local/tmp/{self.args.package}-geckoview-config.yaml'
        result = self.adb.run('shell',shlex.join(['cat',self.state['configPath']]),timeout=30)
        if result.returncode == 0:
            facts = g.transport_config_facts(result.stdout)
            need(facts['transportOnly'] and facts['marionettePort'] == 2828, 'Existing transport config is tainted')
            config = result.stdout
        else:
            need(self.adb.run('shell',shlex.join(['test','-e',self.state['configPath']]),timeout=30).returncode == 1,
                 'Cannot establish absent config')
            local = self.work/'geckoview-config.yaml'; local.write_text(config)
            self.state['configSha256'] = sha(config.encode())
            self.mark('config')
            self.adb.run('push',str(local),self.state['configPath'],check=True,timeout=30)
            self.shell('chmod','644',self.state['configPath'])
        self.state['configSha256'] = sha(config.encode())
        debug = self.shell('settings','get','global','debug_app')
        wait = self.shell('settings','get','global','wait_for_debugger')
        need(debug in ('null','',self.args.package) and wait in ('null','','0'), 'Existing debugger state must be preserved')
        if debug != self.args.package:
            self.mark('debugApp'); self.shell('am','set-debug-app','--persistent',self.args.package)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0))
            self.state['forwardPort'] = listener.getsockname()[1]
        self.save()  # Known port before --no-rebind, even if its response is lost.
        self.connect(restart=True)
        native_prefs = self.client.script(cookie.PREFS_JS, chrome=True)
        cookie.grade_pref_taint(native_prefs)
        self.event('native-policy-before-trust', native_prefs)
        existing = self.cert('read')
        need(existing['matches'] == 0, 'Exact CA already exists; do not modify previous trust')
        self.mark('cert')
        self.state['cert'] = self.cert('import'); self.event('certificate-import',self.state['cert'])
        self.connect(restart=True)
        cert = self.cert('read')
        need(cert['trusted'] and cert['dbKey'] == self.state['cert']['dbKey'], 'CA trust did not survive process restart')
        self.event('certificate-restart-readback',cert)
        self.event('gecko-dns',grade_dns(self.client.script(DNS_JS,[list(NAMES)],chrome=True)))
        for name in NAMES:
            url = 'https://' + name + self.route
            result = self.client.script(cookie.CONTROLLED_ORIGIN_JS,[url],chrome=True)
            self.event('verified-https',cookie.grade_controlled_origin(result,url=url,proof=self.proof,
                                                                     ca_sha256=self.state['caSha256']))
        self.state['status'] = 'TLS_SETUP_VERIFIED_COOKIE_ACCEPTANCE_PENDING'; self.save()
        self.client.close(); self.client = None
        self.stop_bootstrap()  # Cookie runner owns HTTP48761 and its reverse entry.

    def mount_owned(self):
        source = self.state['remoteDir']+'/hosts'
        return owns_mount(mount_entries(self.shell('cat','/proc/self/mountinfo')),
                          self.shell('stat','-c','%d:%i',source), self.shell('stat','-c','%d:%i',HOSTS),
                          self.shell('sha256sum',source).split()[0], self.shell('sha256sum',HOSTS).split()[0],
                          self.state['hostsSha256'])

    def cleanup(self):
        if not any(self.state['owned'].values()) and not self.state.get('appStarted'):
            self.state['cleanupComplete'] = True; self.save(); return
        self.bind_identity()  # Never clean a reused serial on another boot.
        errors = []
        def attempt(name, action):
            try:
                action(); self.state['owned'][name] = False; self.event('cleanup-'+name)
            except Exception as error:
                errors.append(name + ': ' + str(error)); self.event('cleanup-error',errors[-1])
        if self.state['owned'].get('cert'):
            def remove_cert():
                self.installed(); self.connect(restart=True)
                need(not self.cert('remove')['trusted'], 'Fixture CA still trusted after removal')
                self.connect(restart=True)
                result = self.cert('read')
                need(not result['trusted'], 'Removed CA trust returned after process restart')
                self.event('certificate-cleanup-restart',result)
            attempt('cert',remove_cert)
            if errors:
                # Keep the transport needed to recover a partial cert removal.
                self.state['cleanupErrors'] = errors; self.state['cleanupComplete'] = False; self.save()
                raise Pending('Certificate cleanup incomplete; retained owned transport for recovery: ' + '; '.join(errors))
        if self.client:
            self.client.close(); self.client = None
        if self.state.get('appStarted'):
            self.shell('am','force-stop',self.args.package)
            self.state['appStarted'] = False
        attempt('bootstrapReverse',self.stop_bootstrap)
        if self.state['owned'].get('forward') and 'forwardPort' in self.state:
            attempt('forward',lambda:self.remove_route('forward',f"tcp:{self.state['forwardPort']}",'tcp:2828'))
        if self.state['owned'].get('config'):
            def remove_config():
                path = self.state['configPath']
                current = self.adb.run('shell',shlex.join(['cat',path]),timeout=30)
                if current.returncode == 0:
                    need(sha(current.stdout.encode()) == self.state['configSha256'], 'Transport config changed')
                    self.shell('rm',path)
            attempt('config',remove_config)
        if self.state['owned'].get('debugApp'):
            def clear_debug():
                need(self.shell('settings','get','global','debug_app') in ('null','',self.args.package), 'Debug app changed')
                self.shell('am','clear-debug-app')
            attempt('debugApp',clear_debug)
        if self.state['owned'].get('hostsMount'):
            def unmount():
                if mount_entries(self.shell('cat','/proc/self/mountinfo')):
                    need(self.mount_owned(), 'Mounted hosts were replaced; refusing unmount')
                    self.shell('umount',HOSTS)
                need(self.shell('sha256sum',HOSTS).split()[0] == self.state['originalHostsSha256'], 'Original hosts did not return')
            attempt('hostsMount',unmount)
        if self.state['owned'].get('httpsReverse'):
            attempt('httpsReverse',lambda:self.remove_route('reverse','tcp:443','tcp:48762'))
        if self.state['owned'].get('remoteDir') and not self.state['owned'].get('hostsMount'):
            def remove_directory():
                self.shell('rm','-f',self.state['remoteDir']+'/hosts')
                self.shell('rmdir',self.state['remoteDir'])
            attempt('remoteDir',remove_directory)
        if self.state['owned'].get('adbdRoot') and not errors:
            attempt('adbdRoot',lambda:self.adb.run('unroot',check=True,timeout=30))
        self.state['cleanupErrors'] = errors
        self.state['cleanupComplete'] = not errors and not any(self.state['owned'].values())
        self.save()
        need(self.state['cleanupComplete'], 'Cleanup incomplete: ' + '; '.join(errors))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('check-inputs','run','cleanup'))
    parser.add_argument('--ca',type=Path,default=HERE/'fixture-ca.pem')
    parser.add_argument('--manifest',type=Path,default=HERE/'fixture-public-manifest.json')
    parser.add_argument('--adb',default=shutil.which('adb'))
    parser.add_argument('--serial')
    parser.add_argument('--package',default='org.redoubtbrowser')
    parser.add_argument('--apk',type=Path)
    parser.add_argument('--expected-profile')
    parser.add_argument('--fresh-dedicated-profile',action='store_true')
    parser.add_argument('--work',type=Path)
    parser.add_argument('--core-only',action='store_true')
    args = parser.parse_args(argv)
    setup = None
    code = 2
    try:
        if args.action != 'cleanup':
            receipt, encoded = public_inputs(args.ca,args.manifest)
        if args.action == 'check-inputs':
            print(json.dumps({'status':'PUBLIC_INPUTS_VERIFIED_DEVICE_NOT_RUN','manifest':receipt}))
            return 0
        need(args.adb and args.serial and args.work, 'Explicit adb, serial and work directory are required')
        if args.action == 'cleanup':
            state = json.loads((args.work/'setup.json').read_text())
            validate_journal(state)
            need(args.serial == state['serial'], 'Cleanup serial differs from journal')
            args.package, args.expected_profile = state['package'], state['profile']
            validate_profile(args.package,args.expected_profile)
            setup = Setup(args,state)
            setup.cleanup()
            code = 0
            print(json.dumps({'status':'CLEANUP_COMPLETE','journal':str(setup.journal)}))
            return 0
        need(args.apk and args.apk.is_file() and args.expected_profile and args.fresh_dedicated_profile,
             'Exact APK, expected profile and explicit fresh dedicated profile are required')
        validate_profile(args.package,args.expected_profile)
        args.work.mkdir(parents=True,mode=0o700,exist_ok=False)
        setup = Setup(args)
        setup.prepare(receipt,encoded)
        command = [sys.executable,str(ROOT/'scripts/android-cookie-banner-smoke.py'),
                   '--adb',args.adb,'--serial',args.serial,'--package',args.package,'--apk',str(args.apk),
                   '--dedicated-test-profile','--work',str(args.work/'cookie'),
                   '--marionette-port',str(setup.state['forwardPort']),'--fixture-port','48761',
                   '--site-origin','https://cookies.fixture.test','--injection-origin','https://duh.de',
                   '--fixture-ca-sha256',receipt['ca_der_sha256']]
        if args.core_only:
            command.append('--core-only')
        # Preparation proved this reverse absent before handing it to the child.
        # Journal cleanup responsibility before that child can create it, so an
        # interrupted child cannot strand the HTTP reverse needed for recovery.
        setup.mark('bootstrapReverse')
        child = subprocess.Popen(command)
        setup.event('cookie-runner-start',{'pid':child.pid,'argv':command})
        try:
            code = child.wait()
        except BaseException:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=10)
            raise
        setup.state['cookieExitCode'] = code
        setup.event('cookie-runner-exit',code)
    except (Exception, KeyboardInterrupt) as error:
        code = 2
        print('PENDING: ' + str(error),file=sys.stderr)
        if setup:
            setup.state['reason'] = str(error); setup.save()
    finally:
        if setup and args.action != 'cleanup':
            try:
                setup.cleanup()
            except Exception as error:
                code = 2
                print('PENDING cleanup: ' + str(error),file=sys.stderr)
        if setup and args.action != 'cleanup':
            print(json.dumps({'journal':str(setup.journal),'helperExitCode':code,
                              'cookieExitCode':setup.state.get('cookieExitCode'),
                              'cleanupComplete':setup.state.get('cleanupComplete',False),
                              'acceptance':'Cookie runner owns behavior grading; setup never grants full acceptance'}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
