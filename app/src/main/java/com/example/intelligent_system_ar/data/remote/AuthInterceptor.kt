package com.example.intelligent_system_ar.data.remote

import com.example.intelligent_system_ar.data.auth.TokenStore
import okhttp3.Interceptor
import okhttp3.Response

/** Добавляет «Authorization: Bearer <token>» ко всем запросам, кроме самого входа. */
class AuthInterceptor(private val tokenStore: TokenStore) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        // OkHttp 3.x: url() и code() — методы (в OkHttp 4 это были бы свойства)
        if (request.url().encodedPath().endsWith("/auth/token")) return chain.proceed(request)

        val token = tokenStore.token() ?: return chain.proceed(request)
        val response = chain.proceed(
            request.newBuilder().header("Authorization", "Bearer $token").build()
        )
        // 401 — токен недействителен: забываем его, приложение попросит войти заново
        if (response.code() == 401) tokenStore.clear()
        return response
    }
}