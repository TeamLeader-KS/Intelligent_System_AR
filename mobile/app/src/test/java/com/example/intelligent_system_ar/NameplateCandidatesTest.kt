package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.ml.NameplateCandidates
import org.junit.Assert.*
import org.junit.Test

class NameplateCandidatesTest {
    @Test fun keepsExactSerialSpellingWithoutReplacingAmbiguousCharacters() {
        val result=NameplateCandidates.extract("SERIAL No. PUMP_001\nModel PCP60S12/3\nPUMP_001")
        assertTrue(result.contains("PUMP_001"))
        assertTrue(result.contains("PCP60S12/3"))
        assertEquals(1,result.count { it=="PUMP_001" })
        assertFalse(result.contains("SERIAL"))
    }
    @Test fun oversizedTokenIsNotSilentlyTruncated() {
        assertTrue(NameplateCandidates.extract("A".repeat(140)+"001").isEmpty())
    }
    @Test fun longFactorySerialUpTo120CharactersIsPreserved() {
        val serial="SN-"+"A".repeat(95)+"-2026"
        assertTrue(NameplateCandidates.extract("SERIAL $serial").contains(serial))
    }
}
