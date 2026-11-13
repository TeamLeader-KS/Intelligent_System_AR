package com.example.intelligent_system_ar.utils

import android.content.Context
import androidx.core.content.edit

class TokenStorage(context: Context) {
    private val prefs = context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)

    fun saveToken(token: String) {
        prefs.edit { putString("access_token", token) }
    }

    fun getToken(): String? = prefs.getString("access_token", null)

    fun clearToken() {
        prefs.edit { remove("access_token") }
    }
}