package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class DetectResponse(
    @SerializedName("schema_version") val schemaVersion: String,
    @SerializedName("frame_id") val frameId: String,
    @SerializedName("processed_at") val processedAt: String,
    @SerializedName("model") val model: ModelInfo,
    @SerializedName("recognition_status") val recognitionStatus: String,
    @SerializedName("equipment_type") val equipmentType: String?,
    @SerializedName("overall_status") val overallStatus: String,
    @SerializedName("color") val color: String,
    @SerializedName("observations") val observations: List<Observation>,
    @SerializedName("recommendation") val recommendation: Recommendation?,
    @SerializedName("limitations") val limitations: List<String>
)

data class ModelInfo(
    @SerializedName("name") val name: String,
    @SerializedName("version") val version: String,
    @SerializedName("provider") val provider: String
)

data class Observation(
    @SerializedName("id") val id: String,
    @SerializedName("code") val code: String,
    @SerializedName("label_ru") val labelRu: String,
    @SerializedName("bbox") val bbox: BBox,
    @SerializedName("score") val score: Double?,
    @SerializedName("score_kind") val scoreKind: String,
    @SerializedName("requires_review") val requiresReview: Boolean
)

data class BBox(
    @SerializedName("x1") val x1: Float,
    @SerializedName("y1") val y1: Float,
    @SerializedName("x2") val x2: Float,
    @SerializedName("y2") val y2: Float
)

data class Recommendation(
    @SerializedName("template_id") val templateId: String,
    @SerializedName("text_ru") val textRu: String,
    @SerializedName("source") val source: String,
    @SerializedName("approved") val approved: Boolean
)