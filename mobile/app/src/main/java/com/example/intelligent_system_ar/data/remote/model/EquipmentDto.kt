package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class EquipmentDto(
    val id: Int,
    val name: String,
    @SerializedName("workshop_id") val workshopId: Int,
    @SerializedName("inventory_number") val inventoryNumber: String,
    val passport: String,
    @SerializedName("serial_number") val serialNumber: String? = null
)

data class EquipmentCardDto(
    val id: Int,
    val name: String,
    @SerializedName("inventory_number") val inventoryNumber: String,
    val passport: String,
    val components: List<ComponentDto>,
    @SerializedName("serial_number") val serialNumber: String? = null
)

data class ComponentDto(
    val id: Int,
    val revision: Int,
    val name: String,
    val model: String,
    val specifications: List<SpecificationDto>,
    val resource: ResourceDto,
    @SerializedName("runtime_state") val runtimeState: String = "STOPPED",
    @SerializedName("installed_on") val installedOn: String?,
    @SerializedName("last_serviced_at") val lastServicedAt: String?,
    @SerializedName("operating_hours") val operatingHours: Double?,
    @SerializedName("operating_cycles") val operatingCycles: Int?
)

data class SpecificationDto(
    val name: String,
    val value: Double,
    val unit: String,
    val minimum: Double?,
    val maximum: Double?
)

data class ResourceDto(
    val status: String,
    val estimates: Map<String, ResourceMeasureDto>,
    val limitations: String,
    @SerializedName("service_remaining_hours") val serviceRemainingHours: Double?
)

data class ResourceMeasureDto(val norm: Double?, val used: Double?, val remaining: Double?)

data class InspectionHistoryDto(val items: List<InspectionHistoryItemDto>, val total: Int,val limit: Int=20,val offset: Int=0)

data class InspectionHistoryItemDto(
    @SerializedName("inspection_id") val inspectionId: Int,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("processing_status") val processingStatus: String,
    val result: InspectionSummaryDto?
)

data class InspectionSummaryDto(
    val status: String,
    val defect: String,
    val recommendation: String,
    @SerializedName("analysis_source") val analysisSource: String,
    @SerializedName("captured_at") val capturedAt: String? = null,
    val comment: String? = null,
    val diagnostics: List<DiagnosticDto>? = null
)
