package mozilla.components.concept.engine
interface Engine {
  class BrowsingData internal constructor(val types: Int) { companion object {
    const val COOKIES: Int = 1 shl 0; const val DOM_STORAGES = 1 shl 4; const val AUTH_SESSIONS = 1 shl 6
    const val ALL_SITE_SETTINGS = 1 shl 8; const val ALL_CACHES = 1 shl 1
    fun select(vararg types: Int) = BrowsingData(types.sum()) } }
  fun clearData(data: BrowsingData = BrowsingData(0), host: String? = null, onSuccess: (() -> Unit) = { }, onError: ((Throwable) -> Unit) = { }): Unit = Unit
  fun clearTrackingProtectionData(onSuccess: () -> Unit = { }, onError: (Throwable) -> Unit = { }): Unit = Unit
}
