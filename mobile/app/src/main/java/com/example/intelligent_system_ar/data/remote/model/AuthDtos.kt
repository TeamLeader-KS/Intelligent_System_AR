package com.example.intelligent_system_ar.data.remote.model

import com.google.gson.annotations.SerializedName

data class LoginRequest(val login: String, val password: String)

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    val user: AccountDto
)

data class AccountDto(
    val id: Int,
    val login: String,
    @SerializedName("full_name") val fullName: String,
    val role: String,
    @SerializedName("workshop_id") val workshopId: Int?
)

data class NamedDto(val id: Int, val name: String)
