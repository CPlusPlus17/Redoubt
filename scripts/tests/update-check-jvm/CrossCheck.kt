/* Feeds a document and signature produced OUTSIDE the JVM (by
 * scripts/update-manifest.py and openssl, via scripts/sign-update-manifest.sh)
 * through the patch's own UpdateChecker, exactly as the app would receive them.
 *
 *   CrossCheckKt <latest.json> <latest.json.sig> <pubkey base64> <versionName> <versionCode>
 *
 * Prints one of: update <latest_version> <version_code> | uptodate | noresult <reason> */
import mozilla.components.concept.fetch.Client
import mozilla.components.concept.fetch.MutableHeaders
import mozilla.components.concept.fetch.Request
import mozilla.components.concept.fetch.Response
import org.mozilla.fenix.lw.UpdateCheckResult
import org.mozilla.fenix.lw.UpdateChecker
import java.io.ByteArrayInputStream
import java.io.File

private class Files(private val bodies: Map<String, ByteArray>) : Client() {
    override fun fetch(request: Request): Response {
        val body = bodies[request.url]
            ?: return Response(request.url, 404, MutableHeaders(), Response.Body.empty())
        return Response(request.url, 200, MutableHeaders(), Response.Body(ByteArrayInputStream(body)))
    }
}

fun main(args: Array<String>) {
    val endpoint = "https://redoubtbrowser.org/update/android/latest.json"
    val client = Files(mapOf(endpoint to File(args[0]).readBytes(), "$endpoint.sig" to File(args[1]).readBytes()))
    when (val r = UpdateChecker(client, endpoint, args[2].trim(), args[3], args[4].toLong()).check()) {
        is UpdateCheckResult.UpdateAvailable -> println("update ${r.latestVersion} ${r.versionCode}")
        is UpdateCheckResult.UpToDate -> println("uptodate")
        is UpdateCheckResult.NoResult -> println("noresult ${r.reason}")
    }
}
