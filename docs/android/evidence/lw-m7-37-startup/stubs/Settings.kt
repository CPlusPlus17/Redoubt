package org.mozilla.fenix.utils
import org.mozilla.fenix.settings.deletebrowsingdata.DeleteBrowsingDataOnQuitType
class Settings { var shouldDeleteBrowsingDataOnQuit: Boolean = false
  fun getDeleteDataOnQuit(type: DeleteBrowsingDataOnQuitType): Boolean = false }
