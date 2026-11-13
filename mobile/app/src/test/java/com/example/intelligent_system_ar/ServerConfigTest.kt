package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.remote.ServerConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class ServerConfigTest {
    @Test fun normalizesLocalServerAddresses() {
        val expected = "http://192.168.1.50:8001/industrial-vision/api/v1/"
        for (input in listOf("http://192.168.1.50:8001", "http://192.168.1.50:8001/industrial-vision/", expected)) {
            assertEquals(expected, ServerConfig.normalize(input))
        }
        assertEquals("http://10.0.2.2:8000/api/v1/", ServerConfig.normalize("http://10.0.2.2:8000/api/v1"))
    }

    @Test fun rejectsAmbiguousOrCredentialBearingAddresses() {
        for (input in listOf("192.168.1.50", "ftp://host", "http://user:password@host", "http://host?token=abc", "http://host/#fragment", "http://host/another-app")) {
            assertThrows(IllegalArgumentException::class.java) { ServerConfig.normalize(input) }
        }
    }
}
