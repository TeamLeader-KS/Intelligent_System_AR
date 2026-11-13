package com.example.intelligent_system_ar.data.remote

import com.example.intelligent_system_ar.data.auth.TokenStore
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    private lateinit var tokenStore: TokenStore

    /** Вызывается один раз при старте (из MainViewModel). */
    fun init(store: TokenStore) {
        tokenStore = store
    }

    private val http by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .addInterceptor(AuthInterceptor(tokenStore)) // подставляет Bearer-токен
            .build() // логирование тела запросов НЕ включаем: там пароль и токен
    }

    private val retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(ServerConfig.BASE_URL)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    val authApi: AuthApi by lazy { retrofit.create(AuthApi::class.java) }
    val directoryApi: DirectoryApi by lazy { retrofit.create(DirectoryApi::class.java) }
}
