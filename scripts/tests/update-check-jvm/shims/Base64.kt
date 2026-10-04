/* Run-time stand-in for android.util.Base64, whose android.jar copy throws
 * "Stub!". Compiled separately and put BEFORE android.jar on the run-time class
 * path only; callers compiled against android.jar invoke these static methods.
 * DEFAULT decoding tolerates line breaks like Android's; encoding is one line. */
package android.util

object Base64 {
    const val DEFAULT = 0
    const val NO_PADDING = 1
    const val NO_WRAP = 2

    @JvmStatic
    fun decode(str: String, flags: Int): ByteArray = java.util.Base64.getMimeDecoder().decode(str)

    @JvmStatic
    fun encodeToString(input: ByteArray, flags: Int): String = java.util.Base64.getEncoder().encodeToString(input)
}
