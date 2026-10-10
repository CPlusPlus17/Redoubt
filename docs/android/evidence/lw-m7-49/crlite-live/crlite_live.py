exec(open('dbg.py').read())
app.wipe()
out={"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
m=h.open_session(app,"about:blank")
t0=time.time(); polls=[]
while time.time()-t0<300:
    st=m.async_script(h.JS_REVOCATION_STATE, chrome=True)
    polls.append({"t":round(time.time()-t0), "filters": h.crlite_summary(st.get("crliteFilterHashes")), "lm": st.get("certRevocationsLastModified")})
    if isinstance(st.get("crliteFilterHashes"),str) and len(st["crliteFilterHashes"])==64 or "," in str(st.get("crliteFilterHashes")): break
    time.sleep(15)
out["polls"]=polls; out["state_prefs"]=st["prefs"]
res={}
for u in ["https://valid-isrgrootx1.letsencrypt.org/","https://revoked-isrgrootx1.letsencrypt.org/","https://revoked-isrgrootx2.letsencrypt.org/","https://revoked.badssl.com/"]:
    c=h.channel_probe(m,u); ne,pg=h.navigate_observe(m,u)
    res[u]={"channel":c,"navigation_error":ne,"page":{k:pg.get(k) for k in ("url","uri","title","ready")}}
    print(u, c.get("errorCodeString"), c.get("status"), c.get("httpStatus"))
out["sites"]=res
json.dump(out,open('crlite-live.json','w'),indent=1)
print(json.dumps(polls))
m.close(); app.remove_debug_config(); app.force_stop()
