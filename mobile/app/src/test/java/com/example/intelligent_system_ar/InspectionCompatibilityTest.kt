package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.remote.model.InspectionSummaryDto
import com.example.intelligent_system_ar.data.remote.model.SavedInspectionDto
import com.example.intelligent_system_ar.data.remote.model.ServerInspectionDto
import com.example.intelligent_system_ar.data.local.PendingOperation
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
    @Test fun oldQueueDoesNotTurnIntoAnAutomaticVisionRequest() {
        val entry=Gson().fromJson("""{"id":"46f7e6e6-5786-4eb2-83bb-b17b75729731","equipmentId":1,"componentId":2}""",PendingOperation::class.java)
        assertFalse(entry.vision)
        assertTrue(entry.canSend(includeVision=false))
    }
    @Test fun serverFindingsUseVerifiedComponentIdsWithoutInventingClassConfidence() {
        val result=Gson().fromJson("""{"inspection_id":7,"equipment_id":1,"analysis_location":"LOCAL_SERVER","model_version":"local-vlm","status":"WARNING","defect":"Возможный дефект","reason":"Видимый признак","recommendation":"Проверить","detections":[{"component_id":null,"component_name":"Узел не определён","code":"POSSIBLE_LEAK","description":"Возможный след жидкости","box":[0.1,0.2,0.8,0.9],"confidence":null}]}""",ServerInspectionDto::class.java)
        val finding=result.detections.orEmpty().single()
        assertEquals("LOCAL_SERVER",result.analysisLocation)
        assertNull(finding.componentId)
        assertNull(finding.confidence)
        assertEquals("POSSIBLE_LEAK",finding.code)
    }
}
