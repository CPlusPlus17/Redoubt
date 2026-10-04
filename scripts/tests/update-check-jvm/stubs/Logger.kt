/* Compile-only: mozilla.components.support.base.log.logger.Logger (a no-op here). */
package mozilla.components.support.base.log.logger

class Logger(val tag: String? = null) {
    fun debug(message: String, throwable: Throwable? = null) {}
}
