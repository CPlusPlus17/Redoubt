const P=Services.prefs, D=P.getDefaultBranch("");
const g=(b,n,t)=>{try{return t==P.PREF_INT?b.getIntPref(n):b.getCharPref(n)}catch(e){return null}};
const out={appVersion:Services.appinfo.version, buildID:Services.appinfo.appBuildID};
for (const n of ["network.trr.mode","network.trr.uri","network.trr.default_provider_uri","network.trr.custom_uri"]) {
  const t=P.getPrefType(n);
  out[n]={type:t, effective:g(P,n,t), defaultBranch:g(D,n,t), hasUserValue:P.prefHasUserValue(n), locked:P.prefIsLocked(n)};
}
try { out.dnsServiceCurrentTrrURI = Cc["@mozilla.org/network/dns-service;1"].getService(Ci.nsIDNSService).currentTrrURI; out.dnsServiceCurrentTrrMode = Cc["@mozilla.org/network/dns-service;1"].getService(Ci.nsIDNSService).currentTrrMode; } catch(e) { out.dnsServiceErr=String(e); }
return out;
