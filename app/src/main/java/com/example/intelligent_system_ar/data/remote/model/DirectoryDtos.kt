package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class WorkshopDto(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String
)

data class EmployeeDto(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("role") val role: String,
    @SerializedName("workshop_id") val workshopId: Int,
    @SerializedName("can_repair") val canRepair: Boolean
)