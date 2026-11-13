package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.remote.ApiClient
import com.example.intelligent_system_ar.data.remote.model.LoginRequest

class AuthRepository {
    suspend fun login(login: String, password: String): Result<String> {
        return try {
            val response = ApiClient.directoryApi.login(LoginRequest(login, password))
            Result.success(response.accessToken)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}