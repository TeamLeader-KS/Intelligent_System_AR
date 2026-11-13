package com.example.intelligent_system_ar.data.remote

import com.example.intelligent_system_ar.data.remote.model.LoginRequest
import com.example.intelligent_system_ar.data.remote.model.TokenResponse
import retrofit2.http.Body
import retrofit2.http.POST

interface AuthApi {
    /** Вход сотрудника: логин и пароль выдаёт администратор. */
    @POST("auth/token")
    suspend fun login(@Body body: LoginRequest): TokenResponse
}
