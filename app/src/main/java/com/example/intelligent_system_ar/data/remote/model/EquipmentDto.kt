package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class EquipmentDto(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("workshop_id") val workshopId: Int,
    @SerializedName("status") val status: String
)