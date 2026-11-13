package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.auth.TokenStore
import com.example.intelligent_system_ar.data.remote.AuthApi
import com.example.intelligent_system_ar.data.remote.model.LoginRequest
import kotlinx.coroutines.CancellationException
import retrofit2.HttpException
import java.io.IOException

/** Ошибка входа с текстом, который можно показать сотруднику. */
class LoginException(message: String) : Exception(message)

class AuthRepository(
    private val api: AuthApi,
    private val tokenStore: TokenStore
) {
    /** Запрашивает токен и сохраняет его зашифрованным. Пароль нигде не сохраняется. */
    suspend fun login(login: String, password: String): Result<Unit> = try {
        val token = api.login(LoginRequest(login, password)).accessToken
        if (token.isNullOrBlank()) {
            Result.failure(LoginException("Сервер не вернул токен"))
        } else {
            tokenStore.save(token)
            Result.success(Unit)
        }
    } catch (e: CancellationException) {
        throw e
    } catch (e: HttpException) {
        Result.failure(
            LoginException(
                when (e.code()) {
                    400, 401, 422 -> "Неверный логин или пароль"
                    403 -> "Нет разрешения на вход"
                    else -> "Ошибка сервера (${e.code()})"
                }
            )
        )
    } catch (e: IOException) {
        Result.failure(LoginException("Нет связи с сервером. Проверьте интернет"))
    } catch (e: Exception) {
        Result.failure(LoginException("Не удалось войти"))
    }

    fun logout() = tokenStore.clear()
}
