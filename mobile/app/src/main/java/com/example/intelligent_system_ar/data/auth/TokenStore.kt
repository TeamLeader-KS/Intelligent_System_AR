package com.example.intelligent_system_ar.data.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Хранит access_token ТОЛЬКО в зашифрованном виде.
 * Ключ шифрования (AES-256) лежит в Android Keystore и не покидает устройство.
 * Токен действует 8 часов — после этого token() вернёт null и нужно войти заново.
 * Токен и пароль нигде не пишутся в логи.
 */
class TokenStore(context: Context) {

    private val prefs = context.getSharedPreferences("auth_secure", Context.MODE_PRIVATE)

    fun save(token: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString(KEY_IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString(KEY_TOKEN, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putLong(KEY_SAVED_AT, System.currentTimeMillis())
            .apply()
    }

    /** Действующий токен или null (нет токена / истёк срок / не удалось расшифровать). */
    fun token(): String? {
        val iv = prefs.getString(KEY_IV, null) ?: return null
        val data = prefs.getString(KEY_TOKEN, null) ?: return null
        val savedAt = prefs.getLong(KEY_SAVED_AT, 0L)
        if (System.currentTimeMillis() - savedAt > LIFETIME_MS) {
            clear()
            return null
        }
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                secretKey(),
                GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP))
            )
            String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (e: Exception) {
            clear() // ключ потерян или данные повреждены — войти заново
            null
        }
    }

    fun hasValidToken(): Boolean = token() != null

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun secretKey(): SecretKey {
        val ks = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (ks.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "industrial_vision_token_key"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val KEY_IV = "iv"
        const val KEY_TOKEN = "token"
        const val KEY_SAVED_AT = "saved_at"
        // Сервер выдаёт токен на 8 часов; берём с запасом 5 минут
        const val LIFETIME_MS = 8 * 60 * 60 * 1000L - 5 * 60 * 1000L
    }
}
