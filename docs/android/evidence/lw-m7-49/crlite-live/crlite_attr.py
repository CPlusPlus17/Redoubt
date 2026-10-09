exec(open('dbg.py').read())
m=h.open_session(app,"about:blank")   # keep state: filters already synced
out={}
st=m.async_script(h.JS_REVOCATION_STATE, chrome=True); out["filters_before"]=h.crlite_summary(st.get("crliteFilterHashes"))
u="https://revoked.badssl.com/"
out["crlite_mode_2"]=h.channel_probe(m,u+"?a")
m.script('Services.prefs.setIntPref("security.pki.crlite_mode", 0); return 1;', chrome=True)
out["crlite_mode_0"]=h.channel_probe(m,u+"?b")
m.script('Services.prefs.clearUserPref("security.pki.crlite_mode"); return Services.prefs.getIntPref("security.pki.crlite_mode");', chrome=True)
out["crlite_mode_restored"]=h.channel_probe(m,u+"?c")
print(json.dumps({k:(v.get("errorCodeString"),v.get("httpStatus")) if isinstance(v,dict) else v for k,v in out.items()}))
json.dump(out,open('crlite-attribution.json','w'),indent=1)
m.close(); app.remove_debug_config(); app.force_stop()
