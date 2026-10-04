/* Compile-only: the android-components members UpdateCheck.kt uses besides
 * concept-fetch (whose real sources are compiled from the tree). Signatures
 * from the 157 tree: support/utils/.../ext/PackageManagerCompatHelper.kt,
 * support/utils/.../ext/Context.kt, support/base/.../log/logger/Logger.kt. */
package mozilla.components.support.utils.ext

import android.content.Context
import android.content.pm.PackageInfo

interface PackageManagerCompatHelper {
    fun getPackageInfoCompat(packageName: String, flag: Int): PackageInfo
}

val Context.packageManagerCompatHelper: PackageManagerCompatHelper
    get() = throw UnsupportedOperationException("compile-only stub")
