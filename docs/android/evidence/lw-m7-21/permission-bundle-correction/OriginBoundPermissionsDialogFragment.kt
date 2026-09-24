/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

package org.mozilla.fenix.browser.permissions

import android.app.Dialog
import android.content.Context
import android.content.DialogInterface
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.DialogFragment
import androidx.fragment.app.FragmentManager
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import mozilla.components.ExperimentalAndroidComponentsApi
import mozilla.components.browser.state.selector.findTabOrCustomTab
import mozilla.components.browser.state.state.BrowserState
import mozilla.components.browser.state.state.SessionState
import mozilla.components.concept.engine.permission.OriginBoundPermission
import mozilla.components.concept.engine.permission.OriginBoundPermissionRequest
import mozilla.components.concept.engine.permission.SitePermissions.Status
import org.mozilla.fenix.R
import org.mozilla.fenix.ext.requireComponents

/** Shared controls for pending requests and real engine-only persistent/session/private exceptions. */
class OriginBoundPermissionsDialogFragment : DialogFragment() {
    private lateinit var content: LinearLayout
    private var refreshJob: Job? = null
    private var requestsJob: Job? = null
    private var lockJob: Job? = null
    private var decisionDialog: AlertDialog? = null
    private val tabId get() = arguments?.getString(TAB_ID)
    private val privateMode get() = requireArguments().getBoolean(PRIVATE)
    private val contextId get() = arguments?.getString(CONTEXT_ID)

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        content = LinearLayout(requireContext()).apply {
            id = R.id.origin_permissions_dialog_list
            orientation = LinearLayout.VERTICAL
            val padding = (resources.displayMetrics.density * PADDING_DP).toInt()
            setPadding(padding, padding, padding, padding)
        }
        return AlertDialog.Builder(requireContext())
            .setTitle(R.string.origin_permissions_title)
            .setView(ScrollView(requireContext()).apply { addView(content) })
            .setPositiveButton(R.string.origin_permissions_close, null)
            .create()
    }

    override fun onStart() {
        super.onStart()
        requestsJob = lifecycleScope.launch {
            requireComponents.core.store.stateFlow
                .map { state ->
                    (state.tabs + state.customTabs).filter {
                        it.content.private == privateMode && it.contextId == contextId &&
                            (tabId == null || it.id == tabId)
                    }.map { it.id to it.content.permissionRequestsList.map { request -> request.id } }
                }.distinctUntilChanged().collect { refresh() }
        }
        lockJob = lifecycleScope.launch {
            requireComponents.appStore.stateFlow.map { it.isPrivateScreenLocked }
                .distinctUntilChanged().collect { locked ->
                    if (privateMode && locked) dismissAllowingStateLoss()
                }
        }
        refresh()
    }

    override fun onStop() {
        requestsJob?.cancel()
        lockJob?.cancel()
        refreshJob?.cancel()
        super.onStop()
    }

    override fun onDismiss(dialog: DialogInterface) {
        decisionDialog?.dismiss()
        super.onDismiss(dialog)
    }

    override fun onDestroyView() {
        refreshJob?.cancel()
        decisionDialog?.dismiss()
        decisionDialog = null
        super.onDestroyView()
    }

    private fun refresh() {
        refreshJob?.cancel()
        refreshJob = lifecycleScope.launch {
            try {
                val records = requireComponents.core.geckoSitePermissionsStorage
                    .listOriginBoundPermissions(privateMode, contextId)
                if (!isAdded) return@launch
                content.removeAllViews()
                addText(getString(R.string.origin_permissions_default))
                addText(getString(if (privateMode) R.string.origin_permissions_private_scope else R.string.origin_permissions_scope))
                val state = requireComponents.core.store.state
                val pending = originBoundRequests(state, tabId, privateMode, contextId)
                pending.forEach { (requestTabId, request) ->
                    addButton(
                        getString(R.string.origin_permissions_blocked_attempt, kindLabel(request.permission.kind), request.uri),
                        if (request.permission.kind == OriginBoundPermission.Kind.WEBGL) {
                            R.id.origin_permission_pending_webgl
                        } else {
                            R.id.origin_permission_pending_canvas
                        },
                    ) { showDecision(request.permission, request.topLevelOrigin, isRequest = true) { status, permanent ->
                        applyRequest(requestTabId, request, status, permanent)
                    } }
                }
                if (records.isEmpty() && pending.isEmpty()) addText(getString(R.string.origin_permissions_empty))
                records.forEach { record ->
                    addButton(
                        recordLabel(record),
                        if (record.kind == OriginBoundPermission.Kind.WEBGL) {
                            R.id.origin_permission_saved_webgl
                        } else {
                            R.id.origin_permission_saved_canvas
                        },
                    ) {
                        showDecision(record, null) { status, permanent -> applyStored(record, status, permanent) }
                    }
                }
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                showError()
            }
        }
    }

    private fun kindLabel(kind: OriginBoundPermission.Kind) = getString(
        when (kind) {
            OriginBoundPermission.Kind.WEBGL -> R.string.origin_permissions_webgl
            OriginBoundPermission.Kind.CANVAS -> R.string.origin_permissions_canvas
        },
    )

    private fun recordLabel(record: OriginBoundPermission): String = getString(
        R.string.origin_permissions_record,
        kindLabel(record.kind),
        record.origin,
        getString(
            when (record.status) {
                Status.ALLOWED -> R.string.origin_permissions_allowed
                Status.BLOCKED -> R.string.origin_permissions_blocked
                Status.NO_DECISION -> R.string.origin_permissions_ask
            },
        ),
        getString(
            when {
                record.privateMode -> R.string.origin_permissions_private_lifetime
                record.permanent -> R.string.origin_permissions_persistent_lifetime
                else -> R.string.origin_permissions_session_lifetime
            },
        ),
    )

    @OptIn(ExperimentalAndroidComponentsApi::class)
    private fun showDecision(
        record: OriginBoundPermission,
        topLevelOrigin: String?,
        isRequest: Boolean = false,
        onDecision: (Status, Boolean) -> Unit,
    ) {
        if (decisionDialog?.isShowing == true) return
        val body = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.VERTICAL
            val padding = (resources.displayMetrics.density * PADDING_DP).toInt()
            setPadding(padding, padding, padding, padding)
        }
        val message = originBoundRequestMessage(requireContext(), record, topLevelOrigin)
        body.addView(TextView(requireContext()).apply {
            id = R.id.origin_permission_request_origin
            text = message
        })
        body.addView(TextView(requireContext()).apply {
            text = getString(if (record.privateMode) R.string.origin_permissions_private_explanation else R.string.origin_permissions_session_explanation)
        })
        val remember = originBoundRememberChoice(requireContext(), record)
        body.addView(remember)
        decisionDialog = AlertDialog.Builder(requireContext())
            .setTitle(kindLabel(record.kind))
            .setView(body)
            .setPositiveButton(R.string.origin_permissions_allow) { _, _ -> onDecision(Status.ALLOWED, remember.isChecked) }
            .setNegativeButton(R.string.origin_permissions_block) { _, _ -> onDecision(Status.BLOCKED, remember.isChecked) }
            .setNeutralButton(R.string.origin_permissions_ask) { _, _ -> onDecision(Status.NO_DECISION, false) }
            .create().also {
                it.show()
                it.getButton(AlertDialog.BUTTON_POSITIVE).id = R.id.origin_permission_allow
                it.getButton(AlertDialog.BUTTON_NEGATIVE).id = R.id.origin_permission_block
                it.getButton(AlertDialog.BUTTON_NEUTRAL).id =
                    if (isRequest) R.id.origin_permission_ask else R.id.origin_permission_reset
            }
        // Dismissing this view leaves the protected request pending and reachable from site controls.
        pendingRequests().firstOrNull { it.permission == record }?.notifyShown()
    }

    private fun pendingRequests(): List<OriginBoundPermissionRequest> {
        val state = requireComponents.core.store.state
        return originBoundRequests(state, tabId, privateMode, contextId).map { it.second }
    }

    private fun applyRequest(tabId: String, request: OriginBoundPermissionRequest, status: Status, permanent: Boolean) {
        lifecycleScope.launch {
            try {
                val reloaded = applyOriginBoundDecision(requireComponents.core.store, tabId, request, status, permanent)
                if (!reloaded && status != Status.NO_DECISION) {
                    Toast.makeText(context, R.string.origin_permissions_page_changed, Toast.LENGTH_LONG).show()
                }
                refresh()
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                showError()
            }
        }
    }

    private fun applyStored(record: OriginBoundPermission, status: Status, permanent: Boolean) {
        lifecycleScope.launch {
            try {
                val applied = requireComponents.core.geckoSitePermissionsStorage
                    .updateOriginBoundPermission(record, status, permanent)
                if (applied) {
                    // This is explicitly a new user action on the current page, not a promise that
                    // an old exception record still refers to the document that requested it.
                    val requestTabId = tabId
                    if (requestTabId != null) showReload(requestTabId)
                    refresh()
                } else {
                    Toast.makeText(context, R.string.origin_permissions_page_changed, Toast.LENGTH_LONG).show()
                    refresh()
                }
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                showError()
            }
        }
    }

    private fun showReload(requestTabId: String) {
        decisionDialog = AlertDialog.Builder(requireContext())
            .setMessage(R.string.origin_permissions_reload_explanation)
            .setPositiveButton(R.string.origin_permissions_reload) { _, _ ->
                requireComponents.core.store.state.findTabOrCustomTab(requestTabId)?.let { tab ->
                    if (tab.content.private == privateMode && tab.contextId == contextId) {
                        tab.engineState.engineSession?.reload()
                    }
                }
            }
            .setNegativeButton(R.string.origin_permissions_close, null)
            .create().also {
                it.show()
                it.getButton(AlertDialog.BUTTON_POSITIVE).id = R.id.origin_permission_reload
            }
    }

    private fun addText(value: String) {
        content.addView(TextView(requireContext()).apply { text = value })
    }

    private fun addButton(value: String, viewId: Int, action: () -> Unit) {
        content.addView(Button(requireContext()).apply {
            id = viewId
            text = value
            isAllCaps = false
            setOnClickListener { action() }
        })
    }

    private fun showError() {
        if (isAdded) Toast.makeText(context, R.string.origin_permissions_error, Toast.LENGTH_LONG).show()
    }

    companion object {
        private const val TAB_ID = "tabId"
        private const val PRIVATE = "privateMode"
        private const val CONTEXT_ID = "contextId"
        private const val PADDING_DP = 16
        internal const val TAG = "origin-bound-permissions"

        /** Opens permissions for this browsing context; private records never enter normal UI. */
        fun show(manager: FragmentManager, tab: SessionState? = null) {
            if (manager.isStateSaved || manager.findFragmentByTag(TAG) != null) return
            OriginBoundPermissionsDialogFragment().apply {
                arguments = Bundle().apply {
                    putString(TAB_ID, tab?.id)
                    putBoolean(PRIVATE, tab?.content?.private ?: false)
                    putString(CONTEXT_ID, tab?.contextId)
                }
            }.show(manager, TAG)
        }
    }
}

/** Select requests for one explicit browsing context; never expose another tab's private data. */
internal fun originBoundRequests(
    state: BrowserState,
    tabId: String?,
    privateMode: Boolean,
    contextId: String?,
): List<Pair<String, OriginBoundPermissionRequest>> =
    (state.tabs + state.customTabs).filter {
        it.content.private == privateMode && it.contextId == contextId && (tabId == null || it.id == tabId)
    }.flatMap { tab ->
        tab.content.permissionRequestsList.filterIsInstance<OriginBoundPermissionRequest>()
            .filter { it.permission.privateMode == privateMode && it.permission.contextId == contextId }
            .map { tab.id to it }
    }

internal fun originBoundRequestMessage(
    context: Context,
    record: OriginBoundPermission,
    topLevelOrigin: String?,
): String = if (topLevelOrigin != null && topLevelOrigin != record.origin) {
    context.getString(R.string.origin_permissions_frame, record.origin, topLevelOrigin)
} else {
    context.getString(R.string.origin_permissions_origin, record.origin)
}

internal fun originBoundRememberChoice(context: Context, record: OriginBoundPermission) = CheckBox(context).apply {
    id = R.id.origin_permission_remember
    setText(R.string.origin_permissions_remember)
    isChecked = record.permanent && !record.privateMode
    visibility = if (record.privateMode) View.GONE else View.VISIBLE
}
