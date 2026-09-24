#!/usr/bin/env python3
"""Execute actual C++ counter, token helpers, observers and pre/post-init guards.

Only the setter/remover prefixes up to map mutation are compiled; platform,
content-pref IO and container types are mocked. Native xpcshell and GeckoView
instrumentation remain mandatory target gates, not replaced by this harness.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1])
text = (source / 'toolkit/components/cookiebanners/CookieBannerDomainPrefService.cpp').read_text()
canonical = (source / 'docshell/base/CanonicalBrowsingContext.cpp').read_text()


def function(text, marker):
    start = text.index(marker)
    opening = text.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def domain_function(name):
    return function(text, 'nsresult CookieBannerDomainPrefService::' + name + '(')


get = domain_function('GetPrivateSessionToken')
check = domain_function('CheckPrivateSessionToken')
set_guard = domain_function('SetPref').split('  // Create the domain pref data.', 1)[0] + '  ++sets; return NS_OK;\n}'
remove_guard = domain_function('RemovePref').split('  // Clear in-memory domain pref.', 1)[0] + '  ++removes; return NS_OK;\n}'
assert 'EnsureInitCompleted(aIsPrivate)' in set_guard and set_guard.count('CheckPrivateSessionToken') == 2
assert 'EnsureInitCompleted(aIsPrivate)' in remove_guard and remove_guard.count('CheckPrivateSessionToken') == 2
observer = function(text, 'CookieBannerDomainPrefService::Observe(')
observer_body = observer[observer.index('{'):]
decrease = function(canonical, 'static void DecreasePrivateCount()')
accessor = function(canonical, 'uint64_t CanonicalBrowsingContext::PrivateBrowsingSessionGeneration()')
active = function(canonical, 'bool CanonicalBrowsingContext::IsPrivateBrowsingActive()')

prefix = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <utility>
#include <vector>
using nsresult = int;
constexpr int NS_OK = 0, NS_ERROR_NOT_AVAILABLE = 1, NS_ERROR_INVALID_ARG = 2, NS_ERROR_UNEXPECTED = 3;
#define MOZ_ASSERT(x) assert(x)
#define MOZ_ASSERT_UNREACHABLE(x) assert(false)
#define NS_ENSURE_SUCCESS(rv, result) do { if (rv != NS_OK) return result; } while (0)
#define NS_ENSURE_TRUE(test, result) do { if (!(test)) return result; } while (0)
#define NS_WARN_IF(test) (test)
#define MOZ_LOG(...) do {} while (0)
int assertions = 0;
#define CHECK(x) do { ++assertions; assert(x); } while (0)
bool NS_IsMainThread() { return true; }
struct nsACString : std::string {
  void Truncate() { clear(); }
  void AppendInt(uint64_t n) { append(std::to_string(n)); }
  bool Equals(const nsACString& other) const { return *this == other; }
};
using nsAutoCString = nsACString;
static uint32_t gNumberOfPrivateContexts = 0;
static uint64_t gPrivateBrowsingSessionGeneration = 1;
struct nsIObserverService {
  std::vector<std::string> topics;
  std::function<void(const char*)> callback;
  void NotifyObservers(void*, const char* topic, void*) {
    topics.push_back(topic);
    if (callback) callback(topic);
  }
} observerService;
template<typename T> using nsCOMPtr = T*;
namespace mozilla {
struct StaticPrefs {
  inline static bool autostart = false;
  static bool browser_privatebrowsing_autostart() { return autostart; }
};
namespace services { nsIObserverService* GetObserverService() { return &observerService; } }
}
namespace dom { struct CanonicalBrowsingContext {
  static bool IsPrivateBrowsingActive();
  static uint64_t PrivateBrowsingSessionGeneration();
}; }
using dom::CanonicalBrowsingContext;
struct nsICookieBannerService { using Modes = int; };
template<typename T> using RefPtr = std::shared_ptr<T>;
class CookieBannerDomainPrefService {
 public:
  bool mIsInitialized = false, mIsShuttingDown = false, mPrivateSessionObserverRegistered = false;
  bool canInitialize = true;
  int sets = 0, removes = 0;
  std::function<void()> nested;
  void Init() { if (canInitialize) mIsInitialized = mPrivateSessionObserverRegistered = true; }
  void EnsureInitCompleted(bool) { if (nested) { auto f = std::move(nested); nested = nullptr; f(); } }
  struct DomainPrefData { bool mIsPersistent; uint64_t mPrivateSessionGeneration; };
  struct Entry { RefPtr<DomainPrefData> data; const RefPtr<DomainPrefData>& Data() const { return data; } };
  struct Map : std::vector<Entry> {
    template<typename Predicate> void RemoveIf(Predicate p) { erase(std::remove_if(begin(), end(), p), end()); }
  } mPrefsPrivate;
  void AddEntry(bool persistent, uint64_t generation) {
    mPrefsPrivate.push_back({std::make_shared<DomainPrefData>(DomainPrefData{persistent,generation})});
  }
  nsresult GetPrivateSessionToken(nsACString&);
  nsresult CheckPrivateSessionToken(const nsACString&);
  nsresult SetPref(const nsACString&, nsICookieBannerService::Modes, bool, bool, const nsACString*);
  nsresult RemovePref(const nsACString&, bool, const nsACString*);
  nsresult Observe(const char* aTopic)
'''
program = prefix + observer_body + '\n};\n' + '\n'.join([decrease, accessor, active, get, check, set_guard, remove_guard]) + r'''
int main() {
  nsACString domain, token;
  CookieBannerDomainPrefService svc;
  observerService.callback = [&](const char* topic) { svc.Observe(topic); };
  gNumberOfPrivateContexts = 1;
  CHECK(svc.GetPrivateSessionToken(token) == NS_OK && svc.mPrivateSessionObserverRegistered);
  CHECK(svc.SetPref(domain, 0, true, false, &token) == NS_OK && svc.sets == 1);
  CHECK(svc.RemovePref(domain, true, &token) == NS_OK && svc.removes == 1);
  // Both autostart modes advance the actual 1->0 counter generation and clear
  // scoped entries. Autostart retains legacy unscoped and persistent entries.
  for (bool autostart : {false, true}) {
    mozilla::StaticPrefs::autostart = autostart;
    CHECK(svc.GetPrivateSessionToken(token) == NS_OK);
    auto oldGeneration = gPrivateBrowsingSessionGeneration;
    svc.mPrefsPrivate.clear();
    svc.AddEntry(false, oldGeneration);
    svc.AddEntry(false, 0);
    svc.AddEntry(true, 0);
    observerService.topics.clear();
    gNumberOfPrivateContexts = 2;
    DecreasePrivateCount();
    CHECK(gPrivateBrowsingSessionGeneration == oldGeneration && observerService.topics.empty());
    DecreasePrivateCount();
    CHECK(gPrivateBrowsingSessionGeneration == oldGeneration + 1);
    CHECK(svc.mPrefsPrivate.size() == (autostart ? 2 : 1));
    CHECK(observerService.topics.size() == (autostart ? 1 : 2));
    CHECK(observerService.topics.back() == "last-private-context-exited");
    CHECK(svc.SetPref(domain, 0, true, false, &token) == NS_ERROR_NOT_AVAILABLE && svc.sets == 1);
    CHECK(svc.RemovePref(domain, true, &token) == NS_ERROR_NOT_AVAILABLE && svc.removes == 1);
    CHECK(svc.GetPrivateSessionToken(domain) == NS_ERROR_NOT_AVAILABLE);
    gNumberOfPrivateContexts = 1;
    CHECK(svc.SetPref(domain, 0, true, false, &token) == NS_ERROR_NOT_AVAILABLE);
    CHECK(svc.RemovePref(domain, true, &token) == NS_ERROR_NOT_AVAILABLE);
  }
  CHECK(svc.GetPrivateSessionToken(token) == NS_OK);
  svc.nested = [&] { DecreasePrivateCount(); gNumberOfPrivateContexts = 1; };
  CHECK(svc.SetPref(domain, 0, true, false, &token) == NS_ERROR_NOT_AVAILABLE && svc.sets == 1);
  CHECK(svc.GetPrivateSessionToken(token) == NS_OK);
  svc.nested = [&] { DecreasePrivateCount(); gNumberOfPrivateContexts = 1; };
  CHECK(svc.RemovePref(domain, true, &token) == NS_ERROR_NOT_AVAILABLE && svc.removes == 1);
  CHECK(svc.GetPrivateSessionToken(token) == NS_OK);
  svc.nested = [&] { DecreasePrivateCount(); };
  CHECK(svc.SetPref(domain, 0, true, false, &token) == NS_ERROR_NOT_AVAILABLE && svc.sets == 1);
  gNumberOfPrivateContexts = 1;
  CHECK(svc.SetPref(domain, 0, false, false, &token) == NS_ERROR_INVALID_ARG);
  CHECK(svc.SetPref(domain, 0, true, true, &token) == NS_ERROR_INVALID_ARG);
  CHECK(svc.RemovePref(domain, false, &token) == NS_ERROR_INVALID_ARG);
  // A delayed scoped observer must preserve a new generation's entry.
  svc.mPrefsPrivate.clear();
  svc.AddEntry(false, gPrivateBrowsingSessionGeneration - 1);
  svc.AddEntry(false, gPrivateBrowsingSessionGeneration);
  svc.Observe("last-private-context-exited");
  CHECK(svc.mPrefsPrivate.size() == 1);
  CHECK(svc.mPrefsPrivate.front().Data()->mPrivateSessionGeneration == gPrivateBrowsingSessionGeneration);
  // An earlier real legacy-topic observer opens a replacement context and writes
  // its choice before our listener. Both cleanup listeners must preserve it.
  mozilla::StaticPrefs::autostart = false;
  svc.mPrefsPrivate.clear();
  svc.AddEntry(false, 0);
  observerService.callback = [&](const char* topic) {
    if (!strcmp(topic, "last-pb-context-exited")) {
      gNumberOfPrivateContexts = 1;
      svc.AddEntry(false, gPrivateBrowsingSessionGeneration);
    }
    svc.Observe(topic);
  };
  DecreasePrivateCount();
  CHECK(svc.mPrefsPrivate.size() == 1);
  CHECK(svc.mPrefsPrivate.front().Data()->mPrivateSessionGeneration == gPrivateBrowsingSessionGeneration);
  observerService.callback = [&](const char* topic) { svc.Observe(topic); };
  // Existing unscoped normal and persistent-private APIs retain their behavior.
  DecreasePrivateCount();
  CHECK(svc.SetPref(domain, 0, false, false, nullptr) == NS_OK);
  CHECK(svc.RemovePref(domain, false, nullptr) == NS_OK);
  CHECK(svc.SetPref(domain, 0, true, true, nullptr) == NS_OK);
  gNumberOfPrivateContexts = 1;
  svc.mIsShuttingDown = true;
  CHECK(svc.SetPref(domain, 0, true, false, &token) == NS_ERROR_NOT_AVAILABLE);
  CookieBannerDomainPrefService uninitialized;
  uninitialized.canInitialize = false;
  CHECK(uninitialized.GetPrivateSessionToken(token) == NS_ERROR_NOT_AVAILABLE);
  std::cout << "PASS actual C++ counter/token helpers/observers and pre/post-init mutation guards ("
            << assertions << " assertions); platform/IO/container boundaries mocked\n";
}
'''
with tempfile.TemporaryDirectory(prefix='lw23-native-fence-') as tmp:
    cpp = Path(tmp) / 'guard.cpp'
    cpp.write_text(program)
    binary = Path(tmp) / 'guard'
    subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
