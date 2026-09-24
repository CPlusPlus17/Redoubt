package mozilla.components.support.base.log.logger
class Logger(val tag: String) { fun error(message: String, throwable: Throwable? = null) { System.err.println("E/$tag: $message ${throwable?.javaClass?.simpleName}") } }
