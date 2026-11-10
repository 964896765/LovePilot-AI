package com.lovepilot.ai

import org.junit.Assert.assertEquals
import org.junit.Test

class ApiEndpointTest {
    @Test fun httpsEndpointIsNormalized() {
        assertEquals("https://agent.example.com", validateApiEndpoint(" https://agent.example.com/ ", false))
    }
    @Test fun debugLoopbackIsAllowed() {
        assertEquals("http://127.0.0.1:8768", validateApiEndpoint("http://127.0.0.1:8768", true))
    }
    @Test(expected = IllegalArgumentException::class) fun remoteCleartextIsRejected() {
        validateApiEndpoint("http://192.168.1.10:8768", true)
    }
    @Test(expected = IllegalArgumentException::class) fun embeddedCredentialsAreRejected() {
        validateApiEndpoint("https://user:secret@example.com", false)
    }
    @Test(expected = IllegalArgumentException::class) fun redirectsInQueryAreRejected() {
        validateApiEndpoint("https://example.com?url=elsewhere", false)
    }
}
