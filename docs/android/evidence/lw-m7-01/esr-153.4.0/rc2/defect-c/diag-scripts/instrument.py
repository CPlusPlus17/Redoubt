#!/usr/bin/env python3
"""Add temporary DEFC logging to a SCRATCH tree only."""
import sys
root = sys.argv[1] + "/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/browser/"


def edit(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, (path, old[:60], s.count(old))
    open(path, "w").write(s.replace(old, new))


bbf = root + "BaseBrowserFragment.kt"
edit(bbf, """                onQuietRequest = { tabId, _ ->
                    com.google.android.material.snackbar.Snackbar.make(""",
"""                onQuietRequest = { tabId, _ ->
                    android.util.Log.i("DEFC", "quiet frag=${System.identityHashCode(this)} act=${System.identityHashCode(activity)} added=$isAdded attached=${view.isAttachedToWindow} tab=$tabId")
                    com.google.android.material.snackbar.Snackbar.make(""")
edit(bbf, """                    ).setAction(R.string.origin_permissions_review) {
                        store.state.findTabOrCustomTab(tabId)?.let { tab ->""",
"""                    ).setAction(R.string.origin_permissions_review) {
                        android.util.Log.i("DEFC", "review frag=${System.identityHashCode(this)} added=$isAdded detached=$isDetached removing=$isRemoving act=${System.identityHashCode(activity)} tabFound=${store.state.findTabOrCustomTab(tabId) != null} storeHash=${System.identityHashCode(store)} compStore=${System.identityHashCode(requireContext().components.core.store)}")
                        try { android.util.Log.i("DEFC", "review fm=${System.identityHashCode(parentFragmentManager)} saved=${parentFragmentManager.isStateSaved} destroyed=${parentFragmentManager.isDestroyed} tagged=${parentFragmentManager.findFragmentByTag(org.mozilla.fenix.browser.permissions.OriginBoundPermissionsDialogFragment.TAG)}") } catch (e: IllegalStateException) { android.util.Log.i("DEFC", "review fm error", e) }
                        store.state.findTabOrCustomTab(tabId)?.let { tab ->""")
edit(bbf, """        originBoundPermissionsFeature.set(""",
"""        android.util.Log.i("DEFC", "set feature frag=${System.identityHashCode(this)} act=${System.identityHashCode(activity)} store=${System.identityHashCode(store)} tab=${tab.id}")
        originBoundPermissionsFeature.set(""")

dlg = root + "permissions/OriginBoundPermissionsDialogFragment.kt"
edit(dlg, """            if (manager.isStateSaved || manager.findFragmentByTag(TAG) != null) return""",
"""            android.util.Log.i("DEFC", "show fm=${System.identityHashCode(manager)} saved=${manager.isStateSaved} tagged=${manager.findFragmentByTag(TAG)} tab=${tab?.id} private=${tab?.content?.private}")
            if (manager.isStateSaved || manager.findFragmentByTag(TAG) != null) return""")
edit(dlg, """                    if (privateMode && locked) dismissAllowingStateLoss()""",
"""                    android.util.Log.i("DEFC", "lock private=$privateMode locked=$locked")
                    if (privateMode && locked) dismissAllowingStateLoss()""")
edit(dlg, """    override fun onStart() {
        super.onStart()""", """    override fun onStart() {
        super.onStart()
        android.util.Log.i("DEFC", "dialog onStart")""")
edit(dlg, """    override fun onDismiss(dialog: DialogInterface) {""",
"""    override fun onDismiss(dialog: DialogInterface) {
        android.util.Log.i("DEFC", "dialog onDismiss", Throwable("trace"))""")

feat = root + "permissions/OriginBoundPermissionsFeature.kt"
edit(feat, """    override fun start() {""", """    override fun start() {
        android.util.Log.i("DEFC", "feature start ${System.identityHashCode(this)}")""")
edit(feat, """    override fun stop() {""", """    override fun stop() {
        android.util.Log.i("DEFC", "feature stop ${System.identityHashCode(this)}")""")
print("instrumented")
