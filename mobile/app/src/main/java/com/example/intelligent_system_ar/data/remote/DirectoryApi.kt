package com.example.intelligent_system_ar.data.remote

import com.example.intelligent_system_ar.data.remote.model.*
import retrofit2.http.*
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import okhttp3.RequestBody

interface DirectoryApi : AuthApi {
    @Multipart
    @POST("inspections/vision")
    suspend fun analyzeVision(@Header("Authorization") token: String,@Header("Idempotency-Key") key: String,
                              @Part("equipment_id") equipmentId: RequestBody,@Part("source") source: RequestBody,
                              @Part("component_id") componentId: RequestBody?,@Part("captured_at") capturedAt: RequestBody?,
                              @Part image: MultipartBody.Part): ServerInspectionDto

    @GET("inspections/{id}")
    suspend fun serverInspection(@Header("Authorization") token: String,@Path("id") id: Int): ServerInspectionDto
    @Streaming
    @GET("inspections/{id}/export")
    suspend fun exportInspection(@Header("Authorization") token: String,@Path("id") id: Int,
                                 @Query("format") format: String): ResponseBody
    @GET("inspections/{id}")
    suspend fun inspection(@Header("Authorization") token: String,@Path("id") id: Int): SavedInspectionDto
    @POST("inspections/mobile")
    suspend fun saveInspection(@Header("Authorization") token: String, @Header("Idempotency-Key") key: String,
                               @Body body: DeviceInspectionRequest): SavedInspectionDto

    @Multipart
    @POST("inspections/{id}/photo")
    suspend fun attachPhoto(@Header("Authorization") token: String, @Path("id") id: Int,
                            @Part image: MultipartBody.Part)

    @POST("components/{id}/work")
    suspend fun recordWork(@Header("Authorization") token: String, @Path("id") id: Int,
                           @Header("Idempotency-Key") key: String, @Body body: ComponentWorkRequest): ComponentWorkItemDto

    @GET("components/{id}/work")
    suspend fun workHistory(@Header("Authorization") token: String, @Path("id") id: Int,
                            @Query("limit") limit: Int=20,@Query("offset") offset: Int=0): ComponentWorkHistoryDto
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
