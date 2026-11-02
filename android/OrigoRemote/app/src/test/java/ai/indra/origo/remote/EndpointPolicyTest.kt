package ai.indra.origo.remote

import org.junit.Assert.*
import org.junit.Test

class EndpointPolicyTest {
    private val endpoint = "https://workstation.private-tailnet.ts.net"

    @Test fun normalizesTrustedRootEndpoints() {
        assertEquals(endpoint, EndpointPolicy.normalize(" HTTPS://Workstation.Private-Tailnet.ts.net:443/ "))
        assertEquals(endpoint, EndpointPolicy.normalize(endpoint))
    }

    @Test fun rejectsUnsafeOrAmbiguousPairingAddresses() {
        val invalid = listOf(
            "http://workstation.private-tailnet.ts.net", "https://127.0.0.1", "https://example.com",
            "$endpoint:8443", "$endpoint/chat", "$endpoint//", "$endpoint?token=secret", "$endpoint#fragment",
            "https://user@workstation.private-tailnet.ts.net", "https://workstation.private-tailnet.ts.net.evil.example",
            "https://ts.net", "https://.ts.net", "https://bad_label.private-tailnet.ts.net",
            "https://-bad.private-tailnet.ts.net", "https://workstation.private-tailnet.ts.net%2fevil.example",
            "javascript:alert(1)", "file:///data/local/file", "https://workstation.private-tailnet.ts.net/../chat"
        )
        invalid.forEach { assertNull("Accepted unsafe endpoint: $it", EndpointPolicy.normalize(it)) }
    }

    @Test fun navigationAndMicrophoneRequireTheExactOrigin() {
        assertTrue(EndpointPolicy.sameOrigin("$endpoint/chat?session=local", endpoint))
        assertTrue(EndpointPolicy.sameOrigin("$endpoint:443/login", endpoint))
        listOf("http://workstation.private-tailnet.ts.net/chat", "$endpoint:8443/chat",
            "https://another.private-tailnet.ts.net", "https://user@workstation.private-tailnet.ts.net/chat",
            "data:text/html,hello", "about:blank", "$endpoint.evil.example").forEach {
                assertFalse("Accepted foreign origin: $it", EndpointPolicy.sameOrigin(it, endpoint))
            }
    }
}
