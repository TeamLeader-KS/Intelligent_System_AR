package com.example.intelligent_system_ar.data.remote

import okhttp3.HttpUrl

object ServerConfig {
    const val DEFAULT_URL = "http://10.0.2.2:8001/industrial-vision/api/v1/"

    fun normalize(value: String): String {
        val url = HttpUrl.parse(value.trim())
            ?: throw IllegalArgumentException("Введите адрес сервера с http:// или https://")
        require(url.username().isEmpty() && url.password().isEmpty() && url.query() == null && url.fragment() == null) {
            "В адресе не должно быть пароля, параметров или фрагмента"
        }
        val path = url.encodedPath().trimEnd('/')
        val apiPath = when {
            path.isEmpty() -> "/industrial-vision/api/v1/"
            path.endsWith("/api/v1") -> "$path/"
            path == "/industrial-vision" -> "$path/api/v1/"
            else -> throw IllegalArgumentException("Укажите адрес сервера или путь /industrial-vision/api/v1/")
        }
        return url.newBuilder().encodedPath(apiPath).build().toString()
    }
}
