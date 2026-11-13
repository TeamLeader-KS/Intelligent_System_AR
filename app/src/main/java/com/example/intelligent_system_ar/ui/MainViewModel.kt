//package com.example.intelligent_system_ar.ui
//
//import android.app.Application
//import android.content.Context
//import androidx.compose.runtime.getValue
//import androidx.compose.runtime.mutableStateOf
//import androidx.compose.runtime.setValue
//import androidx.lifecycle.AndroidViewModel
//import androidx.lifecycle.viewModelScope
//import com.example.intelligent_system_ar.data.model.DefectMark
//import com.example.intelligent_system_ar.data.model.ScanResult
//import com.example.intelligent_system_ar.data.model.ScanStatus
//import com.example.intelligent_system_ar.data.model.UserState
//import com.example.intelligent_system_ar.data.model.Workshop
//import com.example.intelligent_system_ar.data.local.Employee
//import com.example.intelligent_system_ar.data.remote.ApiClient
//import com.example.intelligent_system_ar.data.remote.ServerConfig
//import com.example.intelligent_system_ar.data.remote.model.BBox
//import com.example.intelligent_system_ar.data.repository.DirectoryRepository
//import com.example.intelligent_system_ar.data.repository.MockDirectoryRepository
//import com.example.intelligent_system_ar.data.repository.RemoteDirectoryRepository
//import kotlinx.coroutines.Job
//import kotlinx.coroutines.delay
//import kotlinx.coroutines.launch
//import java.text.SimpleDateFormat
//import java.util.Date
//import java.util.Locale
//
//class MainViewModel(app: Application) : AndroidViewModel(app) {
//
//    private val prefs = app.getSharedPreferences("user_prefs", Context.MODE_PRIVATE)
//
//    // Сервер или заглушка — переключается в ServerConfig.USE_MOCK
//    private val directory: DirectoryRepository =
//        if (ServerConfig.USE_MOCK) MockDirectoryRepository()
//        else RemoteDirectoryRepository(ApiClient.directoryApi)
//
//    var userState by mutableStateOf(loadUser())
//        private set
//
//    var registration by mutableStateOf(RegistrationUi())
//        private set
//
//    var isScanning by mutableStateOf(false)
//        private set
//
//    // null — ещё не сканировали
//    var scanResult by mutableStateOf<ScanResult?>(null)
//        private set
//
//    // Одноразовое сообщение для Snackbar
//    var event by mutableStateOf<String?>(null)
//        private set
//
//    private var mockIndex = 0
//
//    // ---------- Сохранённый пользователь ----------
//
//    private fun loadUser() = UserState(
//        employeeId = prefs.getInt("id", 0),
//        employeeName = prefs.getString("name", "") ?: "",
//        role = prefs.getString("role", "") ?: "",
//        workshopId = prefs.getInt("workshopId", 0),
//        workshop = prefs.getString("workshop", "") ?: ""
//    )
//
//    private fun saveUser() {
//        prefs.edit()
//            .putInt("id", userState.employeeId)
//            .putString("name", userState.employeeName)
//            .putString("role", userState.role)
//            .putInt("workshopId", userState.workshopId)
//            .putString("workshop", userState.workshop)
//            .apply()
//    }
//
//    // ---------- Регистрация: цех -> должность -> Ф.И.О. ----------
//
//    private var loadToken = 0
//    private var retryAction: (() -> Unit)? = null
//
//    fun openRegistration() {
//        registration = RegistrationUi()
//        loadWorkshops()
//    }
//
//    fun onWorkshopSelected(workshop: Workshop) {
//        registration = registration.copy(
//            selectedWorkshop = workshop,
//            roles = emptyList(), selectedRole = null,
//            employees = emptyList(), selectedEmployee = null
//        )
//        loadRoles(workshop.id)
//    }
//
//    fun onRoleSelected(role: String) {
//        val workshop = registration.selectedWorkshop ?: return
//        registration = registration.copy(
//            selectedRole = role,
//            employees = emptyList(), selectedEmployee = null
//        )
//        loadEmployees(workshop.id, role)
//    }
//
//    fun onEmployeeSelected(employee: Employee) {
//        registration = registration.copy(selectedEmployee = employee)
//    }
//
//    fun retryLoad() {
//        retryAction?.invoke()
//    }
//
//    fun confirmRegistration() {
//        val workshop = registration.selectedWorkshop ?: return
//        val employee = registration.selectedEmployee ?: return
//        userState = UserState(
//            employeeId = employee.id,
//            employeeName = employee.name,
//            role = employee.role,
//            workshopId = workshop.id,
//            workshop = workshop.name
//        )
//        saveUser()
//        event = "Вы вошли как ${employee.name}"
//    }
//
//    private fun loadWorkshops() {
//        retryAction = { loadWorkshops() }
//        load {
//            directory.getWorkshops()
//                .onSuccess { registration = registration.copy(workshops = it) }
//                .onFailure { showLoadError() }
//        }
//    }
//
//    private fun loadRoles(workshopId: Int) {
//        retryAction = { loadRoles(workshopId) }
//        load {
//            directory.getRoles(workshopId)
//                .onSuccess { registration = registration.copy(roles = it) }
//                .onFailure { showLoadError() }
//        }
//    }
//
//    private fun loadEmployees(workshopId: Int, role: String) {
//        retryAction = { loadEmployees(workshopId, role) }
//        load {
//            directory.getEmployees(workshopId, role)
//                .onSuccess { registration = registration.copy(employees = it) }
//                .onFailure { showLoadError() }
//        }
//    }
//
//    private fun showLoadError() {
//        registration = registration.copy(error = "Не удалось загрузить данные с сервера")
//    }
//
//    // token защищает от устаревших ответов, если пользователь быстро меняет выбор
//    private fun load(block: suspend () -> Unit) {
//        val token = ++loadToken
//        registration = registration.copy(isLoading = true, error = null)
//        viewModelScope.launch {
//            block()
//            if (token == loadToken) registration = registration.copy(isLoading = false)
//        }
//    }
//
//    // ---------- Сканирование (заглушки) ----------
//
//    private val mockResults = listOf(
//        // Как на макете: компрессор, поломка двигателя
//        ScanResult(
//            equipmentName = "Компрессор",
//            status = ScanStatus.CRITICAL,
//            equipmentBox = BBox(0.12f, 0.28f, 0.88f, 0.58f),
//            defects = listOf(
//                DefectMark(
//                    title = "Поломка двигателя",
//                    box = BBox(0.18f, 0.30f, 0.46f, 0.43f),
//                    recommendation = "Остановить компрессор и вызвать слесаря для осмотра двигателя."
//                )
//            )
//        ),
//        ScanResult(
//            equipmentName = "Саморез",
//            status = ScanStatus.WARNING,
//            equipmentBox = BBox(0.30f, 0.38f, 0.66f, 0.54f),
//            defects = listOf(
//                DefectMark(
//                    title = "Недокручен",
//                    box = BBox(0.42f, 0.40f, 0.54f, 0.52f),
//                    recommendation = "Докрутить саморез до упора."
//                )
//            )
//        ),
//        ScanResult(
//            equipmentName = "Саморез",
//            status = ScanStatus.CRITICAL,
//            equipmentBox = BBox(0.30f, 0.38f, 0.66f, 0.54f),
//            defects = listOf(
//                DefectMark(
//                    title = "Отсутствует",
//                    box = BBox(0.42f, 0.40f, 0.54f, 0.52f),
//                    recommendation = "Установить новый саморез и сообщить мастеру цеха."
//                )
//            )
//        ),
//        ScanResult(
//            equipmentName = "Компрессор",
//            status = ScanStatus.OK,
//            equipmentBox = BBox(0.12f, 0.28f, 0.88f, 0.58f),
//            defects = emptyList()
//        )
//    )
//
//    private var scanJob: Job? = null
//
//    // TODO: заменить имитацию на запрос /detect (кадр -> DetectResponse -> ScanResult)
//    fun startScan() {
//        if (isScanning) return
//        isScanning = true
//        scanResult = null
//
//        scanJob = viewModelScope.launch {
//            delay(1500)
//            scanResult = mockResults[mockIndex % mockResults.size]
//            mockIndex++
//            isScanning = false
//        }
//    }
//
//    /** Кнопка «Очистить экран»: убирает рамки и карточку, отменяет анализ, если он ещё идёт. */
//    fun clearScreen() {
//        scanJob?.cancel()
//        scanJob = null
//        isScanning = false
//        scanResult = null
//    }
//
//    // TODO: заменить на запрос /alert + запись инцидента в журнал (автор = userState.employeeId)
//    fun sendReport(comment: String) {
//        if (!userState.isRegistered) return
//        val time = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
//        event = "Сообщение отправлено мастеру цеха · $time"
//    }
//
//    fun consumeEvent() {
//        event = null
//    }
//}

package com.example.intelligent_system_ar.ui

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.intelligent_system_ar.data.model.DefectMark
import com.example.intelligent_system_ar.data.model.ScanResult
import com.example.intelligent_system_ar.data.model.ScanStatus
import com.example.intelligent_system_ar.data.model.UserState
import com.example.intelligent_system_ar.data.remote.ApiClient
import com.example.intelligent_system_ar.data.remote.model.BBox
import com.example.intelligent_system_ar.data.remote.model.LoginRequest
import com.example.intelligent_system_ar.data.remote.model.TokenResponse
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.getSharedPreferences("user_prefs", Context.MODE_PRIVATE)

    // --- Состояние авторизации ---
    var accessToken by mutableStateOf<String?>(null)
        private set

    var isLoggingIn by mutableStateOf(false)
        private set

    var loginError by mutableStateOf<String?>(null)
        private set

    // --- Основные состояния ---
    var userState by mutableStateOf(UserState())
        private set

    var isScanning by mutableStateOf(false)
        private set

    var scanResult by mutableStateOf<ScanResult?>(null)
        private set

    var event by mutableStateOf<String?>(null)
        private set

    // ---------- Авторизация ----------

    fun login(login: String, password: String) {
        if (isLoggingIn) return
        isLoggingIn = true
        loginError = null

        viewModelScope.launch {
            try {
                // 1. Отправляем логин и пароль на сервер
                val response = ApiClient.directoryApi.login(LoginRequest(login, password))
                accessToken = response.accessToken

                // 2. Сохраняем токен (в идеале использовать EncryptedSharedPreferences)
                prefs.edit().putString("access_token", response.accessToken).apply()

                event = "Вход выполнен успешно!"
                isLoggingIn = false
            } catch (e: Exception) {
                loginError = "Ошибка входа: ${e.message}"
                isLoggingIn = false
            }
        }
    }

    fun logout() {
        accessToken = null
        prefs.edit().remove("access_token").apply()
        userState = UserState()
        clearScreen()
    }

    fun checkSavedToken() {
        val token = prefs.getString("access_token", null)
        if (token != null) {
            accessToken = token
        }
    }

    // ---------- Сканирование ----------

    private val mockResults = listOf(
        ScanResult(
            equipmentName = "Компрессор",
            status = ScanStatus.CRITICAL,
            equipmentBox = BBox(0.12f, 0.28f, 0.88f, 0.58f),
            defects = listOf(
                DefectMark(
                    title = "Поломка двигателя",
                    box = BBox(0.18f, 0.30f, 0.46f, 0.43f),
                    recommendation = "Остановить компрессор и вызвать слесаря для осмотра двигателя."
                )
            )
        ),
        ScanResult(
            equipmentName = "Саморез",
            status = ScanStatus.WARNING,
            equipmentBox = BBox(0.30f, 0.38f, 0.66f, 0.54f),
            defects = listOf(
                DefectMark(
                    title = "Недокручен",
                    box = BBox(0.42f, 0.40f, 0.54f, 0.52f),
                    recommendation = "Докрутить саморез до упора."
                )
            )
        )
    )

    private var scanJob: Job? = null
    private var mockIndex = 0

    fun startScan() {
        if (isScanning) return
        isScanning = true
        scanResult = null

        scanJob = viewModelScope.launch {
            delay(1500) // Имитация сети
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
        val time = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
        event = "Сообщение отправлено мастеру цеха · $time"
    }

    fun consumeEvent() {
        event = null
    }

    init {
        // При создании ViewModel проверяем, сохранен ли токен
        checkSavedToken()
    }
}