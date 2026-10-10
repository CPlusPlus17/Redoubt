exec(open('dbg.py').read())
m=h.open_session(app,"about:blank")
st=m.async_script(h.JS_REVOCATION_STATE, chrome=True); out={"filters": h.crlite_summary(st.get("crliteFilterHashes"))}
for u in ["https://revoked-isrgrootx1.letsencrypt.org/?x","https://revoked-isrgrootx2.letsencrypt.org/?x"]:
    out[u]=h.channel_probe(m,u)
print(json.dumps({k:(v.get("errorCodeString"),v.get("httpStatus")) if isinstance(v,dict) else v for k,v in out.items()}))
json.dump(out,open('le-revoked-76filters.json','w'),indent=1)
m.close(); app.remove_debug_config(); app.force_stop()
