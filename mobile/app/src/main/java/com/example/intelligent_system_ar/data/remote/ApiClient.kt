package com.example.intelligent_system_ar.data.remote

import android.content.Context
import okhttp3.HttpUrl
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


// Для сервера в локальной сети (192.168.x.x, 10.x.x.x) запросы идут строго через Wi-Fi.
// Для адреса в интернете (https://…) ничего не меняется.

    private fun clientFor(baseUrl: String, context: Context?): OkHttpClient {
        val host = HttpUrl.parse(baseUrl)?.host() ?: return http
        if (context == null || !NetworkBinding.isPrivateIpv4(host)) return http
        return http.newBuilder().socketFactory(WifiSocketFactory(context.applicationContext)).build()
    }

    fun create(baseUrl: String, context: Context? = null): DirectoryApi {
        val normalized = ServerConfig.normalize(baseUrl)
        return Retrofit.Builder()
            .baseUrl(normalized)
            .client(clientFor(normalized, context))
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(DirectoryApi::class.java)
    }
}