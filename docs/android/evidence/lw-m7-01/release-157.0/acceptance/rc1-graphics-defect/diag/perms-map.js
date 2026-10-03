const {E10SUtils} = ChromeUtils.importESModule("resource://gre/modules/E10SUtils.sys.mjs");
const out = {count: 0, failures: [], types: {}};
for (const p of Services.perms.all) {
  out.count++;
  out.types[p.type] = (out.types[p.type] || 0) + 1;
  const row = {type: p.type, origin: (() => { try { return p.principal.origin } catch (e) { return "ERR " + e } })(),
               expireType: p.expireType, isContent: p.principal.isContentPrincipal, schemeIs: (() => { try { return p.principal.URI ? p.principal.URI.scheme : null } catch (e) { return "ERR" } })()};
  try {
    const uri = ["canvas", "webgl"].includes(p.type) ? p.principal.originNoSuffix
              : Services.io.createExposableURI(p.principal.URI).displaySpec;
    E10SUtils.serializePrincipal(p.principal);
    p.principal.originAttributes.geckoViewSessionContextId;
  } catch (e) { row.error = String(e); out.failures.push(row); }
}
return out;
