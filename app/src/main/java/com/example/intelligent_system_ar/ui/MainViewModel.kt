package com.example.intelligent_system_ar.ui

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.intelligent_system_ar.data.auth.TokenStore
import com.example.intelligent_system_ar.data.model.DefectMark
import com.example.intelligent_system_ar.data.model.ScanResult
import com.example.intelligent_system_ar.data.model.ScanStatus
import com.example.intelligent_system_ar.data.model.UserState
import com.example.intelligent_system_ar.data.remote.ApiClient
import com.example.intelligent_system_ar.data.remote.model.BBox
import com.example.intelligent_system_ar.data.repository.AuthRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.getSharedPreferences("user_prefs", Context.MODE_PRIVATE)

    // Токен хранится зашифрованным (Android Keystore). Пароль нигде не сохраняется.
    private val tokenStore = TokenStore(app).also { ApiClient.init(it) }
    private val authRepository = AuthRepository(ApiClient.authApi, tokenStore)

    var userState by mutableStateOf(loadUser())
        private set

    var loginUi by mutableStateOf(LoginUi())
        private set

    var isScanning by mutableStateOf(false)
        private set

    var scanResult by mutableStateOf<ScanResult?>(null)
        private set

    var event by mutableStateOf<String?>(null)
        private set

    private var mockIndex = 0

    // ---------- Сохранённый пользователь ----------

    private fun loadUser() = if (!tokenStore.hasValidToken()) UserState() else UserState(
        login = prefs.getString("login", "") ?: "",
        employeeId = prefs.getInt("id", 0),
        employeeName = prefs.getString("name", "") ?: "",
        role = prefs.getString("role", "") ?: "",
        workshopId = prefs.getInt("workshopId", 0),
        workshop = prefs.getString("workshop", "") ?: ""
    )

    private fun saveUser() {
        prefs.edit()
            .putString("login", userState.login)
            .putInt("id", userState.employeeId)
            .putString("name", userState.employeeName)
            .putString("role", userState.role)
            .putInt("workshopId", userState.workshopId)
            .putString("workshop", userState.workshop)
            .apply()
    }

    // ---------- Вход ----------

    fun login(login: String, password: String, onSuccess: () -> Unit) {
        if (loginUi.isLoading) return
        loginUi = LoginUi(isLoading = true)
        viewModelScope.launch {
            authRepository.login(login, password)
                .onSuccess {
                    userState = UserState(
                        login = login,
                        employeeName = login,
                        role = "—",
                        workshop = "—"
                    )
                    saveUser()
                    loginUi = LoginUi()
                    event = "Вы вошли как $login"
                    onSuccess()
                }
                .onFailure { loginUi = LoginUi(error = it.message ?: "Не удалось войти") }
        }
    }

    fun logout() {
        authRepository.logout()
        userState = UserState()
        saveUser()
    }

    // Новый метод для отображения сообщений из UI (для решения ошибки)
    fun showEvent(message: String) {
        event = message
    }

    // ---------- Сканирование (заглушки) ----------

    private val mockResults = listOf(
        ScanResult(
            equipmentName = "Компрессор",
            status = ScanStatus.CRITICAL,
            equipmentBox = BBox(0.12f, 0.28f, 0.88f, 0.58f),
            defects = listOf(
                DefectMark(
                    title = "Коррозия",
                    box = BBox(0.18f, 0.30f, 0.46f, 0.43f),
                    recommendation = "Остановить компрессор и вызвать слесаря."
                )
            )
        ),
        ScanResult(
            equipmentName = "Насос",
            status = ScanStatus.WARNING,
            equipmentBox = BBox(0.30f, 0.38f, 0.66f, 0.54f),
            defects = listOf(
                DefectMark(
                    title = "Ржавчина",
                    box = BBox(0.42f, 0.40f, 0.54f, 0.52f),
                    recommendation = "Зачистить и покрасить."
                )
            )
        )
    )

    private var scanJob: Job? = null

    fun startScan() {
        if (isScanning) return
        isScanning = true
        scanResult = null

        scanJob = viewModelScope.launch {
            delay(1500)
            scanResult = mockResults[mockIndex % mockResults.size]
            mockIndex++
            isScanning = false
        }
    }

    fun clearScreen() {
        scanJob?.cancel()
        scanJob = null
        isScanning = false
        scanResult = null
    }

    fun sendReport(comment: String) {
        if (!userState.isRegistered) return
        val time = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
        event = "Сообщение отправлено · $time"
    }

    fun consumeEvent() {
        event = null
    }
}