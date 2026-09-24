/* Read-only chrome Marionette ExecuteScript body. Not executed by preparation. */
return (async () => {
  const { AddonManager } = ChromeUtils.importESModule(
    "resource://gre/modules/AddonManager.sys.mjs"
  );
  const id = "uBlock0@raymondhill.net";
  const addon = await AddonManager.getAddonByID(id);
  return {
    observedAt: Date.now(),
    id,
    geckoNewerThanOlder: Services.vc.compare("1.74.0", "1.73.0"),
    signatureEnforcement: Services.prefs.getBoolPref("xpinstall.signatures.required"),
    ordinarySignedStateConstant: AddonManager.SIGNEDSTATE_SIGNED,
    installed: addon ? {
      id: addon.id,
      version: addon.version,
      signedState: addon.signedState,
      ordinarySigned: addon.signedState === AddonManager.SIGNEDSTATE_SIGNED,
      isBuiltin: addon.isBuiltin,
      active: addon.isActive,
      userDisabled: addon.userDisabled,
      appDisabled: addon.appDisabled,
      pendingOperations: addon.pendingOperations,
    } : null,
  };
})();
