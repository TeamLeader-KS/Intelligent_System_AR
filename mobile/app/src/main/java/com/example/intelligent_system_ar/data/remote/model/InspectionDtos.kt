package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class InspectionFrame(val width: Int, val height: Int)
data class DeviceFindingDto(
    @SerializedName("class_id") val classId: Int,
    val confidence: Float,
    val box: List<Float>
)
data class ManualVisualCheck(val code: String,val observed: Boolean=true,val source: String="MANUAL")
data class DeviceInspectionRequest(
    @SerializedName("equipment_id") val equipmentId: Int,
    @SerializedName("component_id") val componentId: Int,
    val source: String = "CAMERA",
    @SerializedName("captured_at") val capturedAt: String,
    @SerializedName("model_sha256") val modelSha256: String,
    val image: InspectionFrame,
    val defects: List<DeviceFindingDto>,
    val comment: String = "",
    @SerializedName("visual_checks") val visualChecks: List<ManualVisualCheck> = emptyList()
)
data class SavedInspectionDto(
    @SerializedName("inspection_id") val inspectionId: Int,
    val status: String,
    val defect: String,
    val recommendation: String,
    val diagnostics: List<DiagnosticDto>? = null,
    @SerializedName("component_resource") val componentResource: ResourceDto? = null
)
data class DiagnosticDto(val code: String,val title: String,val status: String,val recommendation: String)
data class ServerFindingDto(
    @SerializedName("component_id") val componentId: Int?,
    @SerializedName("component_name") val componentName: String?,
    val code: String,
    val description: String,
    val box: List<Float>?,
    val confidence: Double?
)
data class ServerInspectionDto(
    @SerializedName("inspection_id") val inspectionId: Int,
    @SerializedName("equipment_id") val equipmentId: Int,
    @SerializedName("analysis_location") val analysisLocation: String?,
    @SerializedName("model_version") val modelVersion: String?,
    val status: String,
    val defect: String,
    val reason: String,
    val recommendation: String,
    val detections: List<ServerFindingDto>?
)
data class ComponentWorkRequest(
    val action: String,
    @SerializedName("occurred_at") val occurredAt: String,
    @SerializedName("expected_revision") val expectedRevision: Int,
    val comment: String,
    @SerializedName("operating_hours") val operatingHours: Double? = null,
    @SerializedName("operating_cycles") val operatingCycles: Int? = null
)
data class ComponentWorkItemDto(
    @SerializedName("work_id") val workId: Int,
    val action: String,
    val comment: String,
    @SerializedName("recorded_at") val recordedAt: String
)
data class ComponentWorkHistoryDto(val items: List<ComponentWorkItemDto>, val total: Int,val limit: Int=20,val offset: Int=0)
