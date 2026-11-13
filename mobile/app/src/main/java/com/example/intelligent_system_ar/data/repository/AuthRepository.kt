package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.auth.TokenStore
import com.example.intelligent_system_ar.data.remote.AuthApi
import com.example.intelligent_system_ar.data.remote.model.LoginRequest
import com.example.intelligent_system_ar.data.remote.model.TokenResponse
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException
import java.io.IOException
import java.security.GeneralSecurityException

class LoginException(message: String) : Exception(message)

class AuthRepository(private val api: AuthApi, private val tokenStore: TokenStore) {
    suspend fun login(login: String, password: String): Result<TokenResponse> = try {
        val response = api.login(LoginRequest(login, password))
        if (response.accessToken.isBlank()) {
            Result.failure(LoginException("Сервер не вернул токен"))
        } else {
            tokenStore.save(response.accessToken)
            Result.success(response)
        }
    } catch (e: CancellationException) {
        throw e
    } catch (e: HttpException) {
        Result.failure(LoginException(when (e.code()) {
            400, 401, 422 -> "Неверный логин или пароль"
            403 -> "Нет разрешения на вход"
            429 -> "Слишком много попыток. Повторите позже."
            else -> "Ошибка сервера (${e.code()})"
        }))
    } catch (e: IOException) {
        Result.failure(LoginException("Нет связи с локальным сервером. Проверьте Wi-Fi."))
    } catch (e: GeneralSecurityException) {
        Result.failure(LoginException("Не удалось защитить токен в Android Keystore"))
    }

    fun logout() = tokenStore.clear()
}
