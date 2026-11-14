package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class WorkshopDto(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String
)

/** Сотрудник цеха. Имя принимается и как full_name, и как name. */
data class EmployeeDto(
    @SerializedName("id") val id: Int,
    @SerializedName(value = "full_name", alternate = ["name"]) val fullName: String,
    @SerializedName("role") val role: String,
    @SerializedName("workshop_id") val workshopId: Int,
    @SerializedName("can_repair") val canRepair: Boolean = false
)
