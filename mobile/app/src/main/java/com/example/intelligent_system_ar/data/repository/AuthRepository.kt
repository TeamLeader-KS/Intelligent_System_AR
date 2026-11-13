package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.remote.DirectoryApi
import com.example.intelligent_system_ar.data.remote.model.LoginRequest

class AuthRepository(private val api: DirectoryApi) {
    suspend fun login(login: String, password: String): Result<String> =
        safeCall { api.login(LoginRequest(login, password)).accessToken }
}
