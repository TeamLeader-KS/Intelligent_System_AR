package com.example.intelligent_system_ar

import com.example.intelligent_system_ar.data.local.InspectionOutbox
import com.example.intelligent_system_ar.data.local.PendingOperation
import com.example.intelligent_system_ar.data.remote.model.DeviceInspectionRequest
import com.example.intelligent_system_ar.data.remote.model.InspectionFrame
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files
import java.util.UUID

class InspectionOutboxTest {
    private fun operation()=PendingOperation(UUID.randomUUID().toString(),1,inspection=DeviceInspectionRequest(
        equipmentId=1,componentId=2,capturedAt="2026-11-13T10:00:00Z",modelSha256="a".repeat(64),
        image=InspectionFrame(640,480),defects=emptyList()))

    @Test fun photoAndKeySurviveRestartAndPartialUpload() {
        val root=Files.createTempDirectory("iv-outbox").toFile()
        try {
            val entry=operation()
            val first=InspectionOutbox(root,"http://192.168.1.50:8001/industrial-vision/api/v1/",1)
            first.enqueue(entry,byteArrayOf(1,2,3))
            val restarted=InspectionOutbox(root,"http://192.168.1.50:8001/industrial-vision/api/v1/",1)
            assertEquals(entry,restarted.entries().single())
            val saved=restarted.markCreated(entry,42)
            assertEquals(entry.id,saved.id)
            assertEquals(42,restarted.entries().single().inspectionId)
            assertArrayEquals(byteArrayOf(1,2,3),restarted.photo(saved).readBytes())
            restarted.remove(saved)
            assertTrue(restarted.entries().isEmpty())
        } finally { root.deleteRecursively() }
    }

    @Test fun differentServerOrAccountCannotSeeEvidence() {
        val root=Files.createTempDirectory("iv-outbox").toFile()
        try {
            InspectionOutbox(root,"server-a",1).enqueue(operation(),byteArrayOf(9))
            assertTrue(InspectionOutbox(root,"server-a",2).entries().isEmpty())
            assertTrue(InspectionOutbox(root,"server-b",1).entries().isEmpty())
        } finally { root.deleteRecursively() }
    }

    @Test fun serverVisionNeedsExplicitSendAndKeepsOriginalFrameAndKey() {
        val root=Files.createTempDirectory("iv-vision-outbox").toFile()
        try {
            val entry=PendingOperation(UUID.randomUUID().toString(),1,componentId=null,vision=true,capturedAt="2026-11-13T10:00:00Z")
            val queue=InspectionOutbox(root,"local-server",1)
            queue.enqueue(entry,byteArrayOf(3,2,1))
            val restored=InspectionOutbox(root,"local-server",1).entries().single()
            assertEquals(entry,restored)
            assertFalse(restored.canSend(includeVision=false))
            assertTrue(restored.canSend(includeVision=true,visionId=entry.id))
            assertFalse(restored.canSend(includeVision=true,visionId=UUID.randomUUID().toString()))
            assertNull(restored.componentId)
            assertArrayEquals(byteArrayOf(3,2,1),queue.photo(restored).readBytes())
        } finally { root.deleteRecursively() }
    }
}
