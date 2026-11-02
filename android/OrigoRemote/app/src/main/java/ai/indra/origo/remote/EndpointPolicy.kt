package ai.indra.origo.remote

import java.net.URI
import java.util.Locale

/** Pure endpoint policy shared by setup, navigation and permission requests. */
object EndpointPolicy {
    fun normalize(raw: String): String? {
        val uri = runCatching { URI(raw.trim()) }.getOrNull() ?: return null
        val host = uri.host?.lowercase(Locale.ROOT) ?: return null
        if (!uri.scheme.equals("https", ignoreCase = true)) return null
        if (uri.rawUserInfo != null || uri.rawQuery != null || uri.rawFragment != null) return null
        if (uri.rawPath !in listOf("", "/")) return null
        if (uri.port != -1 && uri.port != 443) return null
        if (!host.endsWith(".ts.net") || host.length > 253) return null
        if (!host.split('.').all { it.matches(Regex("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")) }) return null
        return "https://$host"
    }

    fun sameOrigin(candidate: String, endpoint: String): Boolean {
        val uri = runCatching { URI(candidate) }.getOrNull() ?: return false
        val trusted = normalize(endpoint) ?: return false
        if (uri.rawUserInfo != null || !uri.scheme.equals("https", ignoreCase = true)) return false
        val port = uri.port
        if (port != -1 && port != 443) return false
        return "https://${uri.host?.lowercase(Locale.ROOT)}" == trusted
    }
}
