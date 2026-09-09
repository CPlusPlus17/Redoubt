# Add-on controls, completion and signed update audit

Read-only frozen source:
`/home/mgysin/Documents/librewolf/librewolf-153.0esr-1-beta-20260908`.
Input hashes are in `source-inputs.json`. The runner's base commit is
`861362e17309ac73107f5b0ed2c9784042872802`. Source findings below are not claims
that the target APK has compiled or executed them.

## Controls and acknowledged completion

- Fenix `home/intent/HomeDeepLinkIntentProcessor.kt` maps
  `settings_addon_manager` to the add-on manager destination.
- `addons/AddonsManagementFragment.kt` obtains the add-on list and displays
  `add_ons_list`. A-C `feature/addons/ui/AddonsManagerAdapter.kt` binds the
  translated name to `add_on_name` and the selected model's click handler to
  its own `add_on_content_wrapper`; installed models go to
  `InstalledAddonDetailsFragment` through `AddonsManagementView`.
- `addons/InstalledAddonDetailsFragment.kt` and
  `res/layout/fragment_installed_add_on_details.xml` define the exact switches,
  Remove and Report IDs. Checkmarks change before the asynchronous operation.
  Clickability and completion buttons are restored in success/error callbacks;
  success leaves the desired value and updates dependent private-switch
  visibility. Error restores the previous checked value. The runner must check
  those combined conditions, not the optimistic checkmark.
- Remove calls A-C `AddonManager.uninstallAddon` directly. There is no second
  confirmation dialog in this source. The successful callback pops back to the
  manager; failure displays a snackbar and remains on details.
- A-C `feature/addons/AddonManager.kt` calls the matching engine
  enable/disable/uninstall/private-permission API and returns its callbacks.
  `mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs` routes them to
  actual add-on operations. LW-M7-19 changes native JS persistence completion;
  the runner pins its four packaged modules separately.

## Read-only state and private choice

`XPIDatabase.sys.mjs` serializes active/userDisabled/version. XPIStates and its
compressed startup file independently retain enabled state. The runner reads
each without requesting saves, flushing, loading an XPI or registering a test
listener. The live readiness listener count is the production
`redoubtBlockingResponseListeners` introduced by `ubo-readiness.patch`; the
probe does not activate or manufacture that listener.

`GeckoViewWebExtension.setPrivateBrowsingAllowed` awaits
ExtensionPermissions.add/remove for `internal:privateBrowsingAllowed`, reloads
an active extension, then exports its result. Export reads the active policy's
private permission, or ExtensionPermissions when no policy exists.

`toolkit/components/extensions/ExtensionPermissions.sys.mjs` creates its store
using `AppConstants.NIGHTLY_BUILD`. The non-Nightly LegacyPermissionStore writes
`extension-preferences.json` through `JSONFile.saveSoon`; its asynchronous
put/delete returns after scheduling. Its modern PermissionStore awaits the
underlying KeyValueService put/delete instead. This separate legacy store is
outside LW-M7-19's four add-on-state modules. Immediate private-choice persistence
needs its own native completion test; delayed UI inspection cannot settle it.

## Concrete update paths

The ordinary updater is A-C `feature/addons/update/AddonUpdater.kt`:

1. `registerForFutureUpdates` schedules unique periodic WorkManager work for
   supported non-builtin extensions. Immediate `update(id)` schedules a one-time
   worker. The worker awaits WebExtensionSupport initialization, then invokes
   `AddonManager.updateAddon`.
2. That method calls `runtime.updateWebExtension`, which reaches
   `GeckoViewWebExtension.updateWebExtension`. It refreshes stale metadata,
   checks AddonManager.updateEnabled, calls the existing add-on's findUpdates,
   supplies the standard update prompt handler and performs the returned install.
3. A permissions-increasing update follows the existing notification approval
   route. The first engine attempt is cancelled for the prompt; an actual user's
   later approval triggers the second update attempt. A no-update result is a
   distinct status and cannot count as verified update execution.

Fenix `addons/AddonDetailsBindingDelegate.kt` binds a long press on the installed
version to `AddonDetailsFragment.showUpdaterDialog`. This reads the last stored
update attempt and shows information; it is **not** an update trigger.

`debugsettings/addons/ui/AddonsDebugToolsScreen.kt` contains an actual
"Check for updates" button that schedules updates for installed non-builtin
extensions. Availability of that debug drawer is a separate UI setting and is
not assumed in release profiles. The runner does not inject that setting or
replace the public update endpoint.

There is also a concrete user file route. Fenix Settings exposes
`pref_key_install_local_addon` only while `showSecretDebugMenuThisSession` is
enabled through the actual About-screen trigger. Selecting it launches A-C
`AddonFilePicker`, whose ordinary Android document picker accepts XPI/ZIP files.
It calls AddonManager.installAddon with InstallationMethod.FROM_FILE.
GeckoView's normal installWebExtension creates the genuine AddonInstall and
calls installAddonFromAOM; existing signature and permission prompts apply.
Selecting a newer signed version of the same ID exercises the existing verified
install/update path, not the periodic metadata/update-check path.

## Reproducible signed older-to-newer proposal

This is a separate prepared-profile run, before any removal-last lifecycle run:

1. Obtain and archive two **unmodified AMO-signed** uBO XPIs of the same add-on
   ID, older O and newer N. Record each original download URL, SHA256, byte count,
   manifest ID/version and the actual bundled rule used by the parser probe.
   Use Gecko's version comparator to establish N > O. No suitable pair has been
   prepared or verified in this task; do not assume a version mentioned in a unit
   test is an available signed artifact.
2. Prepare a dedicated profile through actual Fenix controls with O installed.
   If replacing the bundled version during setup, remove it through its real
   control first and select O through the real file picker. Keep the preinstall
   completion/removal history intact; never edit its SharedPreferences stamp or
   write profile metadata to force the old version. Reopen and observe O's actual
   ID, version, ordinary AMO signed state and resource behavior.
3. Use the real controls to establish disabled and private-denied choices. On
   another prepared run, establish enabled and private-allowed choices. Select
   the archived N in the real file picker, follow the actual prompts and retain
   UI XML/video plus original bytes. Do not modify an XPI's manifest/update URL,
   counterfeit a signing certificate, change signing prefs or call privileged
   install/update APIs.
4. Require actual O-to-N registry transition and Gecko's signed-state result,
   matching disk/cache versions and retained user choices. Immediately restart
   after a genuine completion event for the native regression; separately keep
   the real UI acknowledgment and timing evidence. The first normal and private
   parser pages must exhibit the retained choices, with independent allowed
   controls and server requests. Missing prompts/completion, unchanged version,
   failed signature or the wrong XPI is not success.
5. Treat periodic-update behavior as additional coverage. For a reproducible
   owned update feed, use a separately AMO-signed test extension with the intended
   update URL already present before signing, two signed versions and a controlled
   HTTPS feed. Do not alter uBO's signed bytes or impersonate AMO to redirect its
   update mechanism. Include real permission notification refusal/approval if
   the signed newer manifest adds permissions.

The current runner deliberately does not implement a fake update success or
read an operator's unvalidated receipt as PASS. Its required `signed-update`
checkpoint remains pending until a source-bound real signed-fixture flow is
implemented and executed. Root may run the proposal manually with explicit
source/APK/artifact bindings; that is separate evidence, not a fabricated result
inside this runner.
