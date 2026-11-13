package com.example.intelligent_system_ar.data.remote

import com.example.intelligent_system_ar.data.remote.model.*
import retrofit2.http.*

interface DirectoryApi : AuthApi {
    @GET("me")
    suspend fun me(@Header("Authorization") token: String): AccountDto

    @GET("workshops")
    suspend fun workshops(@Header("Authorization") token: String): List<NamedDto>

    @GET("equipment")
    suspend fun getEquipment(@Header("Authorization") token: String): List<EquipmentDto>

    @GET("equipment/{id}/card")
    suspend fun card(@Header("Authorization") token: String, @Path("id") id: Int): EquipmentCardDto

    @GET("equipment/resolve")
    suspend fun resolve(@Header("Authorization") token: String, @Query("code") code: String): EquipmentCardDto

    @GET("equipment/{id}/inspections")
    suspend fun history(@Header("Authorization") token: String, @Path("id") id: Int,
                        @Query("limit") limit: Int = 20, @Query("offset") offset: Int = 0): InspectionHistoryDto
}
