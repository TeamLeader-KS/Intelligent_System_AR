package com.example.intelligent_system_ar.data.remote

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    private val http = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        // Не пересылаем пароль и токен на адрес из перенаправления.
        .followRedirects(false)
        .followSslRedirects(false)
        .build()

    fun create(baseUrl: String): DirectoryApi = Retrofit.Builder()
        .baseUrl(ServerConfig.normalize(baseUrl))
        .client(http)
        .addConverterFactory(GsonConverterFactory.create())
        .build()
        .create(DirectoryApi::class.java)
}
