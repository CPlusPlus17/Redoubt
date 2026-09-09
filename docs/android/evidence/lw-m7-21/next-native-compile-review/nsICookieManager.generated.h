/*
 * DO NOT EDIT.  THIS FILE IS GENERATED FROM $SRCDIR/netwerk/cookie
 */

#ifndef __gen_nsICookieManager_h__
#define __gen_nsICookieManager_h__


#include "nsISupports.h"

#include "nsICookie.h"

#include "nsIThirdPartyCookieBlockingExceptionListService.h"

#include "nsIURI.h"

#include "nsTArray.h"

#include "js/Value.h"

/* For IDL files that don't want to include root IDL files. */
#ifndef NS_NO_VTABLE
#define NS_NO_VTABLE
#endif
// %{C++:11-17
#include <functional>
namespace mozilla {
class OriginAttributes;
namespace net {
class CookieStruct;
} // namespace net
} // mozilla namespace
// %}
class nsICookieValidation; /* forward declaration */


/* starting interface:    nsICookieManager */
#define NS_ICOOKIEMANAGER_IID_STR "aaab6710-0f2c-11d5-a53b-0010a401eb10"

#define NS_ICOOKIEMANAGER_IID \
  {0xaaab6710, 0x0f2c, 0x11d5, \
    { 0xa5, 0x3b, 0x00, 0x10, 0xa4, 0x01, 0xeb, 0x10 }}

class nsICookieManager : public nsISupports {
 public:

  NS_INLINE_DECL_STATIC_IID(NS_ICOOKIEMANAGER_IID)

  /* Used by ToJSValue to check which scriptable interface is implemented. */
  using ScriptableInterfaceType = nsICookieManager;

  /* ACString beginSessionCleanup (); */
  NS_IMETHOD BeginSessionCleanup(nsACString& _retval) = 0;

  /* [implicit_jscontext] Promise getSessionCleanupScopes (in ACString aToken); */
  NS_IMETHOD GetSessionCleanupScopes(const nsACString& aToken, JSContext* cx, ::mozilla::dom::Promise * * _retval) = 0;

  /* [implicit_jscontext] Promise removeSessionCleanupScopes (in ACString aToken, in Array<unsigned long> aScopeIds); */
  NS_IMETHOD RemoveSessionCleanupScopes(const nsACString& aToken, const nsTArray<uint32_t >& aScopeIds, JSContext* cx, ::mozilla::dom::Promise * * _retval) = 0;

  /* void endSessionCleanup (in ACString aToken); */
  NS_IMETHOD EndSessionCleanup(const nsACString& aToken) = 0;

  /* void removeAll (); */
  NS_IMETHOD RemoveAll(void) = 0;

  /* readonly attribute Array<nsICookie> cookies; */
  NS_IMETHOD GetCookies(nsTArray<RefPtr<nsICookie>>& aCookies) = 0;

  /* readonly attribute Array<nsICookie> sessionCookies; */
  NS_IMETHOD GetSessionCookies(nsTArray<RefPtr<nsICookie>>& aSessionCookies) = 0;

  /* uint32_t getCookieBehavior (in boolean aIsPrivate); */
  NS_IMETHOD GetCookieBehavior(bool aIsPrivate, uint32_t *_retval) = 0;

// %{C++:96-96
    static uint32_t GetCookieBehavior(bool aIsPrivate);
// %}
  /* [implicit_jscontext] void remove (in AUTF8String aHost, in ACString aName, in AUTF8String aPath, in jsval aOriginAttributes); */
  NS_IMETHOD Remove(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx) = 0;

  /* [notxpcom] nsresult removeNative (in AUTF8String aHost, in ACString aName, in AUTF8String aPath, in OriginAttributesPtr aOriginAttributes, in boolean aFromHttp, in nsIDPtr aOperationID); */
  NS_IMETHOD RemoveNative(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, mozilla::OriginAttributes * aOriginAttributes, bool aFromHttp, const nsID * aOperationID) = 0;

  /* [implicit_jscontext] nsICookieValidation add (in AUTF8String aHost, in AUTF8String aPath, in ACString aName, in AUTF8String aValue, in boolean aIsSecure, in boolean aIsHttpOnly, in boolean aIsSession, in int64_t aExpiry, in jsval aOriginAttributes, in int32_t aSameSite, in nsICookie_schemeType aSchemeMap, [optional] in boolean aIsPartitioned); */
  NS_IMETHOD Add(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, JS::Handle<JS::Value> aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, JSContext* cx, nsICookieValidation **_retval) = 0;

  /* [notxpcom] nsresult addNative (in nsIURI aCookieURI, in AUTF8String aHost, in AUTF8String aPath, in ACString aName, in AUTF8String aValue, in boolean aIsSecure, in boolean aIsHttpOnly, in boolean aIsSession, in int64_t aExpiry, in OriginAttributesPtr aOriginAttributes, in int32_t aSameSite, in nsICookie_schemeType aSchemeMap, in boolean aIsPartitioned, in boolean aFromHttp, in nsIDPtr aOperationID, out nsICookieValidation aValidation); */
  NS_IMETHOD AddNative(nsIURI *aCookieURI, const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, mozilla::OriginAttributes * aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, bool aFromHttp, const nsID * aOperationID, nsICookieValidation **aValidation) = 0;

  /* [implicit_jscontext] boolean cookieExists (in AUTF8String aHost, in AUTF8String aPath, in ACString aName, in jsval aOriginAttributes); */
  NS_IMETHOD CookieExists(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx, bool *_retval) = 0;

  /* [notxpcom] nsresult cookieExistsNative (in AUTF8String aHost, in AUTF8String aPath, in ACString aName, in OriginAttributesPtr aOriginAttributes, out boolean aExists); */
  NS_IMETHOD CookieExistsNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, bool *aExists) = 0;

  /* [notxpcom] nsresult getCookieNative (in AUTF8String aHost, in AUTF8String aPath, in ACString aName, in OriginAttributesPtr aOriginAttributes, out nsICookie aCookie); */
  NS_IMETHOD GetCookieNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, nsICookie **aCookie) = 0;

  /* unsigned long countCookiesFromHost (in AUTF8String aHost); */
  NS_IMETHOD CountCookiesFromHost(const nsACString& aHost, uint32_t *_retval) = 0;

  /* boolean hasCookiesForSite (in AUTF8String aHost, in AString aPattern); */
  NS_IMETHOD HasCookiesForSite(const nsACString& aHost, const nsAString& aPattern, bool *_retval) = 0;

  /* [implicit_jscontext] Array<nsICookie> getCookiesFromHost (in AUTF8String aHost, in jsval aOriginAttributes, [optional] in boolean aSorted); */
  NS_IMETHOD GetCookiesFromHost(const nsACString& aHost, JS::Handle<JS::Value> aOriginAttributes, bool aSorted, JSContext* cx, nsTArray<RefPtr<nsICookie>>& _retval) = 0;

  /* [notxpcom] nsresult getCookiesFromHostNative (in AUTF8String aHost, in OriginAttributesPtr aOriginAttributes, in boolean aSorted, out Array<nsICookie> aCookies); */
  NS_IMETHOD GetCookiesFromHostNative(const nsACString& aHost, mozilla::OriginAttributes * aOriginAttributes, bool aSorted, nsTArray<RefPtr<nsICookie>>& aCookies) = 0;

  /* Array<nsICookie> getCookiesWithOriginAttributes (in AString aPattern, [optional] in AUTF8String aHost, [optional] in boolean aSorted); */
  NS_IMETHOD GetCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost, bool aSorted, nsTArray<RefPtr<nsICookie>>& _retval) = 0;

  /* void removeCookiesWithOriginAttributes (in AString aPattern, [optional] in AUTF8String aHost); */
  NS_IMETHOD RemoveCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost) = 0;

  /* void removeCookiesFromExactHost (in AUTF8String aHost, in AString aPattern); */
  NS_IMETHOD RemoveCookiesFromExactHost(const nsACString& aHost, const nsAString& aPattern) = 0;

  /* [implicit_jscontext] Promise removeAllSince (in int64_t aSinceWhen); */
  NS_IMETHOD RemoveAllSince(int64_t aSinceWhen, JSContext* cx, ::mozilla::dom::Promise * * _retval) = 0;

  /* Array<nsICookie> getCookiesSince (in int64_t aSinceWhen); */
  NS_IMETHOD GetCookiesSince(int64_t aSinceWhen, nsTArray<RefPtr<nsICookie>>& _retval) = 0;

  /* void addThirdPartyCookieBlockingExceptions (in Array<nsIThirdPartyCookieExceptionEntry> aExcpetions); */
  NS_IMETHOD AddThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExcpetions) = 0;

  /* void removeThirdPartyCookieBlockingExceptions (in Array<nsIThirdPartyCookieExceptionEntry> aExceptions); */
  NS_IMETHOD RemoveThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExceptions) = 0;

  /* Array<ACString> testGet3PCBExceptions (); */
  NS_IMETHOD TestGet3PCBExceptions(nsTArray<nsCString >& _retval) = 0;

  /* void testCloseCookieDB (); */
  NS_IMETHOD TestCloseCookieDB(void) = 0;

  /* void testOpenCookieDB (); */
  NS_IMETHOD TestOpenCookieDB(void) = 0;

  /* int64_t maybeCapExpiry (in int64_t aExpiryInMSec); */
  NS_IMETHOD MaybeCapExpiry(int64_t aExpiryInMSec, int64_t *_retval) = 0;

};


/* Use this macro when declaring classes that implement this interface. */
#define NS_DECL_NSICOOKIEMANAGER \
  NS_IMETHOD BeginSessionCleanup(nsACString& _retval) override; \
  NS_IMETHOD GetSessionCleanupScopes(const nsACString& aToken, JSContext* cx, ::mozilla::dom::Promise * * _retval) override; \
  NS_IMETHOD RemoveSessionCleanupScopes(const nsACString& aToken, const nsTArray<uint32_t >& aScopeIds, JSContext* cx, ::mozilla::dom::Promise * * _retval) override; \
  NS_IMETHOD EndSessionCleanup(const nsACString& aToken) override; \
  NS_IMETHOD RemoveAll(void) override; \
  NS_IMETHOD GetCookies(nsTArray<RefPtr<nsICookie>>& aCookies) override; \
  NS_IMETHOD GetSessionCookies(nsTArray<RefPtr<nsICookie>>& aSessionCookies) override; \
  NS_IMETHOD GetCookieBehavior(bool aIsPrivate, uint32_t *_retval) override; \
  NS_IMETHOD Remove(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx) override; \
  NS_IMETHOD RemoveNative(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, mozilla::OriginAttributes * aOriginAttributes, bool aFromHttp, const nsID * aOperationID) override; \
  NS_IMETHOD Add(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, JS::Handle<JS::Value> aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, JSContext* cx, nsICookieValidation **_retval) override; \
  NS_IMETHOD AddNative(nsIURI *aCookieURI, const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, mozilla::OriginAttributes * aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, bool aFromHttp, const nsID * aOperationID, nsICookieValidation **aValidation) override; \
  NS_IMETHOD CookieExists(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx, bool *_retval) override; \
  NS_IMETHOD CookieExistsNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, bool *aExists) override; \
  NS_IMETHOD GetCookieNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, nsICookie **aCookie) override; \
  NS_IMETHOD CountCookiesFromHost(const nsACString& aHost, uint32_t *_retval) override; \
  NS_IMETHOD HasCookiesForSite(const nsACString& aHost, const nsAString& aPattern, bool *_retval) override; \
  NS_IMETHOD GetCookiesFromHost(const nsACString& aHost, JS::Handle<JS::Value> aOriginAttributes, bool aSorted, JSContext* cx, nsTArray<RefPtr<nsICookie>>& _retval) override; \
  NS_IMETHOD GetCookiesFromHostNative(const nsACString& aHost, mozilla::OriginAttributes * aOriginAttributes, bool aSorted, nsTArray<RefPtr<nsICookie>>& aCookies) override; \
  NS_IMETHOD GetCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost, bool aSorted, nsTArray<RefPtr<nsICookie>>& _retval) override; \
  NS_IMETHOD RemoveCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost) override; \
  NS_IMETHOD RemoveCookiesFromExactHost(const nsACString& aHost, const nsAString& aPattern) override; \
  NS_IMETHOD RemoveAllSince(int64_t aSinceWhen, JSContext* cx, ::mozilla::dom::Promise * * _retval) override; \
  NS_IMETHOD GetCookiesSince(int64_t aSinceWhen, nsTArray<RefPtr<nsICookie>>& _retval) override; \
  NS_IMETHOD AddThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExcpetions) override; \
  NS_IMETHOD RemoveThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExceptions) override; \
  NS_IMETHOD TestGet3PCBExceptions(nsTArray<nsCString >& _retval) override; \
  NS_IMETHOD TestCloseCookieDB(void) override; \
  NS_IMETHOD TestOpenCookieDB(void) override; \
  NS_IMETHOD MaybeCapExpiry(int64_t aExpiryInMSec, int64_t *_retval) override; 

/* Use this macro when declaring the members of this interface when the
   class doesn't implement the interface. This is useful for forwarding. */
#define NS_DECL_NON_VIRTUAL_NSICOOKIEMANAGER \
  nsresult BeginSessionCleanup(nsACString& _retval); \
  nsresult GetSessionCleanupScopes(const nsACString& aToken, JSContext* cx, ::mozilla::dom::Promise * * _retval); \
  nsresult RemoveSessionCleanupScopes(const nsACString& aToken, const nsTArray<uint32_t >& aScopeIds, JSContext* cx, ::mozilla::dom::Promise * * _retval); \
  nsresult EndSessionCleanup(const nsACString& aToken); \
  nsresult RemoveAll(void); \
  nsresult GetCookies(nsTArray<RefPtr<nsICookie>>& aCookies); \
  nsresult GetSessionCookies(nsTArray<RefPtr<nsICookie>>& aSessionCookies); \
  nsresult GetCookieBehavior(bool aIsPrivate, uint32_t *_retval); \
  nsresult Remove(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx); \
  nsresult RemoveNative(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, mozilla::OriginAttributes * aOriginAttributes, bool aFromHttp, const nsID * aOperationID); \
  nsresult Add(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, JS::Handle<JS::Value> aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, JSContext* cx, nsICookieValidation **_retval); \
  nsresult AddNative(nsIURI *aCookieURI, const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, mozilla::OriginAttributes * aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, bool aFromHttp, const nsID * aOperationID, nsICookieValidation **aValidation); \
  nsresult CookieExists(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx, bool *_retval); \
  nsresult CookieExistsNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, bool *aExists); \
  nsresult GetCookieNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, nsICookie **aCookie); \
  nsresult CountCookiesFromHost(const nsACString& aHost, uint32_t *_retval); \
  nsresult HasCookiesForSite(const nsACString& aHost, const nsAString& aPattern, bool *_retval); \
  nsresult GetCookiesFromHost(const nsACString& aHost, JS::Handle<JS::Value> aOriginAttributes, bool aSorted, JSContext* cx, nsTArray<RefPtr<nsICookie>>& _retval); \
  nsresult GetCookiesFromHostNative(const nsACString& aHost, mozilla::OriginAttributes * aOriginAttributes, bool aSorted, nsTArray<RefPtr<nsICookie>>& aCookies); \
  nsresult GetCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost, bool aSorted, nsTArray<RefPtr<nsICookie>>& _retval); \
  nsresult RemoveCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost); \
  nsresult RemoveCookiesFromExactHost(const nsACString& aHost, const nsAString& aPattern); \
  nsresult RemoveAllSince(int64_t aSinceWhen, JSContext* cx, ::mozilla::dom::Promise * * _retval); \
  nsresult GetCookiesSince(int64_t aSinceWhen, nsTArray<RefPtr<nsICookie>>& _retval); \
  nsresult AddThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExcpetions); \
  nsresult RemoveThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExceptions); \
  nsresult TestGet3PCBExceptions(nsTArray<nsCString >& _retval); \
  nsresult TestCloseCookieDB(void); \
  nsresult TestOpenCookieDB(void); \
  nsresult MaybeCapExpiry(int64_t aExpiryInMSec, int64_t *_retval); 

/* Use this macro to declare functions that forward the behavior of this interface to another object. */
#define NS_FORWARD_NSICOOKIEMANAGER(_to) \
  NS_IMETHOD BeginSessionCleanup(nsACString& _retval) override { return _to BeginSessionCleanup(_retval); } \
  NS_IMETHOD GetSessionCleanupScopes(const nsACString& aToken, JSContext* cx, ::mozilla::dom::Promise * * _retval) override { return _to GetSessionCleanupScopes(aToken, cx, _retval); } \
  NS_IMETHOD RemoveSessionCleanupScopes(const nsACString& aToken, const nsTArray<uint32_t >& aScopeIds, JSContext* cx, ::mozilla::dom::Promise * * _retval) override { return _to RemoveSessionCleanupScopes(aToken, aScopeIds, cx, _retval); } \
  NS_IMETHOD EndSessionCleanup(const nsACString& aToken) override { return _to EndSessionCleanup(aToken); } \
  NS_IMETHOD RemoveAll(void) override { return _to RemoveAll(); } \
  NS_IMETHOD GetCookies(nsTArray<RefPtr<nsICookie>>& aCookies) override { return _to GetCookies(aCookies); } \
  NS_IMETHOD GetSessionCookies(nsTArray<RefPtr<nsICookie>>& aSessionCookies) override { return _to GetSessionCookies(aSessionCookies); } \
  NS_IMETHOD GetCookieBehavior(bool aIsPrivate, uint32_t *_retval) override { return _to GetCookieBehavior(aIsPrivate, _retval); } \
  NS_IMETHOD Remove(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx) override { return _to Remove(aHost, aName, aPath, aOriginAttributes, cx); } \
  NS_IMETHOD RemoveNative(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, mozilla::OriginAttributes * aOriginAttributes, bool aFromHttp, const nsID * aOperationID) override { return _to RemoveNative(aHost, aName, aPath, aOriginAttributes, aFromHttp, aOperationID); } \
  NS_IMETHOD Add(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, JS::Handle<JS::Value> aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, JSContext* cx, nsICookieValidation **_retval) override { return _to Add(aHost, aPath, aName, aValue, aIsSecure, aIsHttpOnly, aIsSession, aExpiry, aOriginAttributes, aSameSite, aSchemeMap, aIsPartitioned, cx, _retval); } \
  NS_IMETHOD AddNative(nsIURI *aCookieURI, const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, mozilla::OriginAttributes * aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, bool aFromHttp, const nsID * aOperationID, nsICookieValidation **aValidation) override { return _to AddNative(aCookieURI, aHost, aPath, aName, aValue, aIsSecure, aIsHttpOnly, aIsSession, aExpiry, aOriginAttributes, aSameSite, aSchemeMap, aIsPartitioned, aFromHttp, aOperationID, aValidation); } \
  NS_IMETHOD CookieExists(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx, bool *_retval) override { return _to CookieExists(aHost, aPath, aName, aOriginAttributes, cx, _retval); } \
  NS_IMETHOD CookieExistsNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, bool *aExists) override { return _to CookieExistsNative(aHost, aPath, aName, aOriginAttributes, aExists); } \
  NS_IMETHOD GetCookieNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, nsICookie **aCookie) override { return _to GetCookieNative(aHost, aPath, aName, aOriginAttributes, aCookie); } \
  NS_IMETHOD CountCookiesFromHost(const nsACString& aHost, uint32_t *_retval) override { return _to CountCookiesFromHost(aHost, _retval); } \
  NS_IMETHOD HasCookiesForSite(const nsACString& aHost, const nsAString& aPattern, bool *_retval) override { return _to HasCookiesForSite(aHost, aPattern, _retval); } \
  NS_IMETHOD GetCookiesFromHost(const nsACString& aHost, JS::Handle<JS::Value> aOriginAttributes, bool aSorted, JSContext* cx, nsTArray<RefPtr<nsICookie>>& _retval) override { return _to GetCookiesFromHost(aHost, aOriginAttributes, aSorted, cx, _retval); } \
  NS_IMETHOD GetCookiesFromHostNative(const nsACString& aHost, mozilla::OriginAttributes * aOriginAttributes, bool aSorted, nsTArray<RefPtr<nsICookie>>& aCookies) override { return _to GetCookiesFromHostNative(aHost, aOriginAttributes, aSorted, aCookies); } \
  NS_IMETHOD GetCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost, bool aSorted, nsTArray<RefPtr<nsICookie>>& _retval) override { return _to GetCookiesWithOriginAttributes(aPattern, aHost, aSorted, _retval); } \
  NS_IMETHOD RemoveCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost) override { return _to RemoveCookiesWithOriginAttributes(aPattern, aHost); } \
  NS_IMETHOD RemoveCookiesFromExactHost(const nsACString& aHost, const nsAString& aPattern) override { return _to RemoveCookiesFromExactHost(aHost, aPattern); } \
  NS_IMETHOD RemoveAllSince(int64_t aSinceWhen, JSContext* cx, ::mozilla::dom::Promise * * _retval) override { return _to RemoveAllSince(aSinceWhen, cx, _retval); } \
  NS_IMETHOD GetCookiesSince(int64_t aSinceWhen, nsTArray<RefPtr<nsICookie>>& _retval) override { return _to GetCookiesSince(aSinceWhen, _retval); } \
  NS_IMETHOD AddThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExcpetions) override { return _to AddThirdPartyCookieBlockingExceptions(aExcpetions); } \
  NS_IMETHOD RemoveThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExceptions) override { return _to RemoveThirdPartyCookieBlockingExceptions(aExceptions); } \
  NS_IMETHOD TestGet3PCBExceptions(nsTArray<nsCString >& _retval) override { return _to TestGet3PCBExceptions(_retval); } \
  NS_IMETHOD TestCloseCookieDB(void) override { return _to TestCloseCookieDB(); } \
  NS_IMETHOD TestOpenCookieDB(void) override { return _to TestOpenCookieDB(); } \
  NS_IMETHOD MaybeCapExpiry(int64_t aExpiryInMSec, int64_t *_retval) override { return _to MaybeCapExpiry(aExpiryInMSec, _retval); } 

/* Use this macro to declare functions that forward the behavior of this interface to another object in a safe way. */
#define NS_FORWARD_SAFE_NSICOOKIEMANAGER(_to) \
  NS_IMETHOD BeginSessionCleanup(nsACString& _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->BeginSessionCleanup(_retval); } \
  NS_IMETHOD GetSessionCleanupScopes(const nsACString& aToken, JSContext* cx, ::mozilla::dom::Promise * * _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetSessionCleanupScopes(aToken, cx, _retval); } \
  NS_IMETHOD RemoveSessionCleanupScopes(const nsACString& aToken, const nsTArray<uint32_t >& aScopeIds, JSContext* cx, ::mozilla::dom::Promise * * _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->RemoveSessionCleanupScopes(aToken, aScopeIds, cx, _retval); } \
  NS_IMETHOD EndSessionCleanup(const nsACString& aToken) override { return !_to ? NS_ERROR_NULL_POINTER : _to->EndSessionCleanup(aToken); } \
  NS_IMETHOD RemoveAll(void) override { return !_to ? NS_ERROR_NULL_POINTER : _to->RemoveAll(); } \
  NS_IMETHOD GetCookies(nsTArray<RefPtr<nsICookie>>& aCookies) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCookies(aCookies); } \
  NS_IMETHOD GetSessionCookies(nsTArray<RefPtr<nsICookie>>& aSessionCookies) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetSessionCookies(aSessionCookies); } \
  NS_IMETHOD GetCookieBehavior(bool aIsPrivate, uint32_t *_retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCookieBehavior(aIsPrivate, _retval); } \
  NS_IMETHOD Remove(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx) override { return !_to ? NS_ERROR_NULL_POINTER : _to->Remove(aHost, aName, aPath, aOriginAttributes, cx); } \
  NS_IMETHOD RemoveNative(const nsACString& aHost, const nsACString& aName, const nsACString& aPath, mozilla::OriginAttributes * aOriginAttributes, bool aFromHttp, const nsID * aOperationID) override; \
  NS_IMETHOD Add(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, JS::Handle<JS::Value> aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, JSContext* cx, nsICookieValidation **_retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->Add(aHost, aPath, aName, aValue, aIsSecure, aIsHttpOnly, aIsSession, aExpiry, aOriginAttributes, aSameSite, aSchemeMap, aIsPartitioned, cx, _retval); } \
  NS_IMETHOD AddNative(nsIURI *aCookieURI, const nsACString& aHost, const nsACString& aPath, const nsACString& aName, const nsACString& aValue, bool aIsSecure, bool aIsHttpOnly, bool aIsSession, int64_t aExpiry, mozilla::OriginAttributes * aOriginAttributes, int32_t aSameSite, nsICookie::schemeType aSchemeMap, bool aIsPartitioned, bool aFromHttp, const nsID * aOperationID, nsICookieValidation **aValidation) override; \
  NS_IMETHOD CookieExists(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, JS::Handle<JS::Value> aOriginAttributes, JSContext* cx, bool *_retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->CookieExists(aHost, aPath, aName, aOriginAttributes, cx, _retval); } \
  NS_IMETHOD CookieExistsNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, bool *aExists) override; \
  NS_IMETHOD GetCookieNative(const nsACString& aHost, const nsACString& aPath, const nsACString& aName, mozilla::OriginAttributes * aOriginAttributes, nsICookie **aCookie) override; \
  NS_IMETHOD CountCookiesFromHost(const nsACString& aHost, uint32_t *_retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->CountCookiesFromHost(aHost, _retval); } \
  NS_IMETHOD HasCookiesForSite(const nsACString& aHost, const nsAString& aPattern, bool *_retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->HasCookiesForSite(aHost, aPattern, _retval); } \
  NS_IMETHOD GetCookiesFromHost(const nsACString& aHost, JS::Handle<JS::Value> aOriginAttributes, bool aSorted, JSContext* cx, nsTArray<RefPtr<nsICookie>>& _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCookiesFromHost(aHost, aOriginAttributes, aSorted, cx, _retval); } \
  NS_IMETHOD GetCookiesFromHostNative(const nsACString& aHost, mozilla::OriginAttributes * aOriginAttributes, bool aSorted, nsTArray<RefPtr<nsICookie>>& aCookies) override; \
  NS_IMETHOD GetCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost, bool aSorted, nsTArray<RefPtr<nsICookie>>& _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCookiesWithOriginAttributes(aPattern, aHost, aSorted, _retval); } \
  NS_IMETHOD RemoveCookiesWithOriginAttributes(const nsAString& aPattern, const nsACString& aHost) override { return !_to ? NS_ERROR_NULL_POINTER : _to->RemoveCookiesWithOriginAttributes(aPattern, aHost); } \
  NS_IMETHOD RemoveCookiesFromExactHost(const nsACString& aHost, const nsAString& aPattern) override { return !_to ? NS_ERROR_NULL_POINTER : _to->RemoveCookiesFromExactHost(aHost, aPattern); } \
  NS_IMETHOD RemoveAllSince(int64_t aSinceWhen, JSContext* cx, ::mozilla::dom::Promise * * _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->RemoveAllSince(aSinceWhen, cx, _retval); } \
  NS_IMETHOD GetCookiesSince(int64_t aSinceWhen, nsTArray<RefPtr<nsICookie>>& _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCookiesSince(aSinceWhen, _retval); } \
  NS_IMETHOD AddThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExcpetions) override { return !_to ? NS_ERROR_NULL_POINTER : _to->AddThirdPartyCookieBlockingExceptions(aExcpetions); } \
  NS_IMETHOD RemoveThirdPartyCookieBlockingExceptions(const nsTArray<RefPtr<nsIThirdPartyCookieExceptionEntry>>& aExceptions) override { return !_to ? NS_ERROR_NULL_POINTER : _to->RemoveThirdPartyCookieBlockingExceptions(aExceptions); } \
  NS_IMETHOD TestGet3PCBExceptions(nsTArray<nsCString >& _retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->TestGet3PCBExceptions(_retval); } \
  NS_IMETHOD TestCloseCookieDB(void) override { return !_to ? NS_ERROR_NULL_POINTER : _to->TestCloseCookieDB(); } \
  NS_IMETHOD TestOpenCookieDB(void) override { return !_to ? NS_ERROR_NULL_POINTER : _to->TestOpenCookieDB(); } \
  NS_IMETHOD MaybeCapExpiry(int64_t aExpiryInMSec, int64_t *_retval) override { return !_to ? NS_ERROR_NULL_POINTER : _to->MaybeCapExpiry(aExpiryInMSec, _retval); } 


#endif /* __gen_nsICookieManager_h__ */
