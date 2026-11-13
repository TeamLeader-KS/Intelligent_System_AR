package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class EquipmentDto(
    val id: Int,
    val name: String,
    @SerializedName("workshop_id") val workshopId: Int,
    @SerializedName("inventory_number") val inventoryNumber: String,
    val passport: String
)

data class EquipmentCardDto(
    val id: Int,
    val name: String,
    @SerializedName("inventory_number") val inventoryNumber: String,
    val passport: String,
    val components: List<ComponentDto>
)

data class ComponentDto(
    val name: String,
    val model: String,
    val specifications: List<SpecificationDto>,
    val resource: ResourceDto
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

data class InspectionHistoryDto(val items: List<InspectionHistoryItemDto>, val total: Int)

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
    @SerializedName("analysis_source") val analysisSource: String
)
