package com.lovepilot.ai

import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Explicit USB setup. The credential arrives at runtime, outside the APK. */
class DeviceProvisioningTest {
    @Test fun saveAuthorizedUsbConnection() {
        val arguments = InstrumentationRegistry.getArguments()
        val token = arguments.getString("provision_token")
        assumeTrue("Explicit device setup credential required", !token.isNullOrBlank())
        val url = arguments.getString("provision_url") ?: "http://127.0.0.1:8768"
        val prefs = SecurePrefs(InstrumentationRegistry.getInstrumentation().targetContext)
        prefs.saveConnection(validateApiEndpoint(url, true), token!!)
        assertTrue("Encrypted credential roundtrip failed", token == prefs.read("token"))
        assertEquals(url, prefs.read("url"))
    }
}
