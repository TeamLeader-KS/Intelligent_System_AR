package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.remote.model.InspectionSummaryDto
import com.example.intelligent_system_ar.data.remote.model.SavedInspectionDto
import com.google.gson.Gson
import org.junit.Assert.*
import org.junit.Test

class InspectionCompatibilityTest {
    @Test fun oldHistoryWithoutDiagnosticsRemainsReadable() {
        val item=Gson().fromJson("""{"status":"WARNING","defect":"Ржавчина","recommendation":"Проверить поверхность","analysis_source":"MODEL"}""",InspectionSummaryDto::class.java)
        assertTrue(item.diagnostics.orEmpty().isEmpty())
        assertEquals("Ржавчина",item.defect)
    }
    @Test fun oldInspectionWithoutDiagnosticsRemainsReadable() {
        val item=Gson().fromJson("""{"inspection_id":42,"status":"WARNING","defect":"Ржавчина","recommendation":"Проверить поверхность"}""",SavedInspectionDto::class.java)
        assertTrue(item.diagnostics.orEmpty().isEmpty())
        assertNull(item.componentResource)
        assertEquals(42,item.inspectionId)
    }
}
