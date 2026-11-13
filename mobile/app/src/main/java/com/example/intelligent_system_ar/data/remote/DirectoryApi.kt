package com.example.intelligent_system_ar.data.remote

import com.example.intelligent_system_ar.data.remote.model.EquipmentDto
import com.example.intelligent_system_ar.data.remote.model.LoginRequest
import com.example.intelligent_system_ar.data.remote.model.TokenResponse
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface DirectoryApi {

    /** Авторизация. Получение токена по логину и паролю. */
    @POST("auth/token")
    suspend fun login(@Body request: LoginRequest): TokenResponse

    /** Получение списка оборудования текущего цеха. */
    @GET("equipment")
    suspend fun getEquipment(
        @Header("Authorization") bearerToken: String // Передаем "Bearer <token>"
    ): List<EquipmentDto>
}