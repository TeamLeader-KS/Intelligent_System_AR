package com.example.intelligent_system_ar.ui

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.intelligent_system_ar.data.local.Employee
import com.example.intelligent_system_ar.data.model.UserState
import com.example.intelligent_system_ar.data.model.Workshop
import com.example.intelligent_system_ar.data.model.roleTitle
import com.example.intelligent_system_ar.data.auth.TokenStore
import com.example.intelligent_system_ar.data.repository.AuthRepository
import com.example.intelligent_system_ar.data.repository.DirectoryRepository
import com.example.intelligent_system_ar.data.repository.LoginException
import com.example.intelligent_system_ar.data.repository.MockDirectoryRepository
import com.example.intelligent_system_ar.data.repository.ServerDirectoryRepository
import com.example.intelligent_system_ar.data.repository.StaffSource
import com.example.intelligent_system_ar.data.remote.ApiClient
import com.example.intelligent_system_ar.data.remote.DirectoryApi
import com.example.intelligent_system_ar.data.remote.ServerConfig
import com.example.intelligent_system_ar.data.remote.model.*
import com.google.gson.JsonParseException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("local_server_session", Context.MODE_PRIVATE)
    private val tokenStore = TokenStore(app)
    var serverUrl by mutableStateOf(prefs.getString("server_url", ServerConfig.DEFAULT_URL)!!)
        private set
    private var api = ApiClient.create(serverUrl, app)

    var accessToken by mutableStateOf<String?>(null)
        private set
    var isLoggingIn by mutableStateOf(false)
        private set
    var loginError by mutableStateOf<String?>(null)
        private set
    var userState by mutableStateOf(UserState())
        private set
    var equipment by mutableStateOf<List<EquipmentDto>>(emptyList())
        private set
    var card by mutableStateOf<EquipmentCardDto?>(null)
        private set
    var history by mutableStateOf<InspectionHistoryDto?>(null)
        private set
    var isLoadingEquipment by mutableStateOf(false)
        private set
    var isLoadingCard by mutableStateOf(false)
        private set
    var isLoadingHistory by mutableStateOf(false)
        private set
    var equipmentError by mutableStateOf<String?>(null)
        private set
    var cardError by mutableStateOf<String?>(null)
        private set
    var historyError by mutableStateOf<String?>(null)
        private set
    var event by mutableStateOf<String?>(null)
        private set

    private var sessionJob: Job? = null
    private var equipmentJob: Job? = null
    private var cardJob: Job? = null
    private var historyJob: Job? = null

    // Откуда берутся цеха / должности / сотрудники для окна регистрации (см. StaffSource.USE_MOCK)
    private val staff: DirectoryRepository =
        if (StaffSource.USE_MOCK) MockDirectoryRepository()
        else ServerDirectoryRepository(api = { api }, token = { accessToken })

    /** Оборудование выбранного цеха. В режиме заглушки не фильтруем: id цехов заглушки не совпадают с серверными. */
    val visibleEquipment: List<EquipmentDto>
        get() = if (StaffSource.USE_MOCK || userState.workshopId == 0) equipment
        else equipment.filter { it.workshopId == userState.workshopId }

    fun login(address: String, login: String, password: String) {
        if (isLoggingIn) return
        val normalized = try {
            ServerConfig.normalize(address)
        } catch (e: IllegalArgumentException) {
            loginError = e.message
            return
        }
        serverUrl = normalized
        api = ApiClient.create(normalized, getApplication())
        tokenStore.clear()
        prefs.edit().putString("server_url", normalized).remove("access_token").apply()
        authenticate { client ->
            AuthRepository(client, tokenStore).login(login.trim(), password).getOrThrow().let { it.accessToken to it.user }
        }
    }

    fun restoreSession() {
        if (isLoggingIn) return
        val saved = tokenStore.token() ?: return
        authenticate { client -> saved to client.me("Bearer $saved") }
    }

    private fun authenticate(load: suspend (DirectoryApi) -> Pair<String, AccountDto>) {
        sessionJob = viewModelScope.launch {
            isLoggingIn = true
            loginError = null
            try {
                val (token, user) = load(api)
                userState = withActing(user.toUserState())
                accessToken = token
                refreshEquipment()
            } catch (e: LoginException) {
                loginError = e.message
            } catch (e: HttpException) {
                if (e.code() == 401) tokenStore.clear()
                loginError = message(e)
            } catch (e: IOException) {
                loginError = message(e)
            } catch (e: JsonParseException) {
                loginError = "Ответ сервера не соответствует приложению"
            } finally {
                isLoggingIn = false
            }
        }
    }

    fun logout() {
        sessionJob?.cancel()
        equipmentJob?.cancel()
        cardJob?.cancel()
        historyJob?.cancel()
        accessToken = null
        tokenStore.clear()
        prefs.edit().remove("access_token").apply()
        clearActing()
        userState = UserState()
        equipment = emptyList()
        card = null
        history = null
        equipmentError = null
        cardError = null
        historyError = null
        event = null
        isLoggingIn = false
        isLoadingEquipment = false
        isLoadingCard = false
        isLoadingHistory = false
    }

    fun refreshEquipment() {
        val token = accessToken ?: return
        equipmentJob?.cancel()
        equipmentJob = viewModelScope.launch {
            isLoadingEquipment = true
            equipmentError = null
            try {
                equipment = api.getEquipment("Bearer $token")
                val shops = api.workshops("Bearer $token")
                userState = userState.copy(workshop = shops.firstOrNull { it.id == userState.workshopId }?.name
                    ?: if (userState.workshopId == 0) "Все цеха" else "Цех №${userState.workshopId}")
            } catch (e: HttpException) {
                equipmentError = authenticatedError(e)
            } catch (e: IOException) {
                equipmentError = message(e)
            } catch (e: JsonParseException) {
                equipmentError = "Не удалось прочитать список оборудования"
            } finally {
                isLoadingEquipment = false
            }
        }
    }

    fun selectEquipment(id: Int) = loadCard { token -> api.card(token, id) }

    fun resolveEquipment(code: String) {
        if (code.isBlank()) return
        loadCard { token -> api.resolve(token, code.trim()) }
    }

    private fun loadCard(load: suspend (String) -> EquipmentCardDto) {
        val token = accessToken ?: return
        cardJob?.cancel()
        historyJob?.cancel()
        card = null
        history = null
        historyError = null
        isLoadingHistory = false
        cardJob = viewModelScope.launch {
            isLoadingCard = true
            cardError = null
            try {
                card = load("Bearer $token")
            } catch (e: HttpException) {
                cardError = authenticatedError(e)
            } catch (e: IOException) {
                cardError = message(e)
            } catch (e: JsonParseException) {
                cardError = "Не удалось прочитать карточку оборудования"
            } finally {
                isLoadingCard = false
            }
        }
    }

    fun loadHistory() {
        val token = accessToken ?: return
        val id = card?.id ?: return
        historyJob?.cancel()
        historyJob = viewModelScope.launch {
            isLoadingHistory = true
            historyError = null
            try {
                history = api.history("Bearer $token", id)
            } catch (e: HttpException) {
                historyError = authenticatedError(e)
            } catch (e: IOException) {
                historyError = message(e)
            } catch (e: JsonParseException) {
                historyError = "Не удалось прочитать историю осмотров"
            } finally {
                isLoadingHistory = false
            }
        }
    }

    fun consumeEvent() { event = null }

    // ---------- Смена цеха / должности / ФИО после входа ----------
    // Логин и пароль вводятся один раз. Дальше сотрудник просто выбирает: цех -> должность -> Ф.И.О.

    var registration by mutableStateOf(RegistrationUi())
        private set

    private var roleCodes: Map<String, String> = emptyMap() // «Мастер» -> значение для запроса к серверу
    private var loadToken = 0
    private var retryAction: (() -> Unit)? = null

    fun openRegistration() {
        registration = RegistrationUi()
        loadWorkshops()
    }

    fun onWorkshopSelected(workshop: Workshop) {
        roleCodes = emptyMap()
        registration = registration.copy(
            selectedWorkshop = workshop,
            roles = emptyList(), selectedRole = null,
            employees = emptyList(), selectedEmployee = null
        )
        loadRoles(workshop.id)
    }

    fun onRoleSelected(title: String) {
        val workshop = registration.selectedWorkshop ?: return
        registration = registration.copy(
            selectedRole = title,
            employees = emptyList(), selectedEmployee = null
        )
        loadEmployees(workshop.id, roleCodes[title] ?: title)
    }

    fun onEmployeeSelected(employee: Employee) {
        registration = registration.copy(selectedEmployee = employee)
    }

    fun retryLoad() {
        retryAction?.invoke()
    }

    fun confirmRegistration() {
        val workshop = registration.selectedWorkshop ?: return
        val employee = registration.selectedEmployee ?: return
        userState = userState.copy(
            employeeId = employee.id,
            employeeName = employee.name,
            role = roleTitle(employee.role),
            workshopId = workshop.id,
            workshop = workshop.name
        )
        saveActing()
        event = "Теперь работает: ${employee.name}"
    }

    private fun loadWorkshops() {
        retryAction = { loadWorkshops() }
        loadStaff {
            staff.getWorkshops()
                .onSuccess { registration = registration.copy(workshops = it) }
                .onFailure { showStaffError(it) }
        }
    }

    private fun loadRoles(workshopId: Int) {
        retryAction = { loadRoles(workshopId) }
        loadStaff {
            staff.getRoles(workshopId)
                .onSuccess { codes ->
                    val byTitle = codes.associateBy { roleTitle(it) }
                    roleCodes = byTitle
                    registration = registration.copy(roles = byTitle.keys.toList())
                }
                .onFailure { showStaffError(it) }
        }
    }

    private fun loadEmployees(workshopId: Int, role: String) {
        retryAction = { loadEmployees(workshopId, role) }
        loadStaff {
            staff.getEmployees(workshopId, role)
                .onSuccess { registration = registration.copy(employees = it) }
                .onFailure { showStaffError(it) }
        }
    }

    private fun showStaffError(e: Throwable) {
        val text = when {
            e is HttpException && e.code() == 404 ->
                "На сервере ещё нет этого списка (нужны workshops/{id}/roles и workshops/{id}/employees)"
            e is HttpException && e.code() == 401 -> "Сессия истекла. Выйдите и войдите снова"
            e is HttpException -> "Сервер вернул ошибку ${e.code()}"
            else -> "Не удалось загрузить список. Проверьте связь с сервером"
        }
        registration = registration.copy(error = text)
    }

    // token защищает индикатор загрузки от «устаревших» запросов при быстрой смене выбора
    private fun loadStaff(block: suspend () -> Unit) {
        val token = ++loadToken
        registration = registration.copy(isLoading = true, error = null)
        viewModelScope.launch {
            block()
            if (token == loadToken) registration = registration.copy(isLoading = false)
        }
    }

    // Выбор запоминается: после перезапуска приложения цех/должность/ФИО остаются прежними
    private fun saveActing() {
        prefs.edit()
            .putString("acting_login", userState.login)
            .putInt("acting_id", userState.employeeId)
            .putString("acting_name", userState.employeeName)
            .putString("acting_role", userState.role)
            .putInt("acting_workshop_id", userState.workshopId)
            .putString("acting_workshop", userState.workshop)
            .apply()
    }

    private fun clearActing() {
        prefs.edit().remove("acting_login").remove("acting_id").remove("acting_name")
            .remove("acting_role").remove("acting_workshop_id").remove("acting_workshop").apply()
    }

    private fun withActing(base: UserState): UserState {
        if (prefs.getString("acting_login", null) != base.login) return base
        val id = prefs.getInt("acting_id", 0)
        if (id == 0) return base
        return base.copy(
            employeeId = id,
            employeeName = prefs.getString("acting_name", null) ?: base.employeeName,
            role = prefs.getString("acting_role", null) ?: base.role,
            workshopId = prefs.getInt("acting_workshop_id", base.workshopId),
            workshop = prefs.getString("acting_workshop", null) ?: base.workshop
        )
    }

    private fun AccountDto.toUserState() = UserState(
        login = login,
        employeeId = id, employeeName = fullName, workshopId = workshopId ?: 0,
        workshop = if (workshopId == null) "Все цеха" else "Цех №$workshopId",
        role = when (role) {
            "ADMIN" -> "Администратор"
            "WORKER" -> "Рабочий"
            "MASTER" -> "Мастер"
            "ENGINEER" -> "Инженер"
            "HEAD" -> "Руководитель"
            else -> role
        }
    )

    private fun authenticatedError(e: HttpException): String {
        if (e.code() == 401) {
            logout()
            loginError = "Сессия истекла. Войдите снова."
        }
        return message(e)
    }

    private fun message(e: Exception): String = when (e) {
        is HttpException -> when (e.code()) {
            401 -> "Неверный логин, пароль или истёкший токен"
            403 -> "Нет доступа к этим данным"
            404 -> "Оборудование или API не найдено. Проверьте адрес сервера."
            429 -> "Слишком много попыток. Повторите позже."
            else -> "Сервер вернул ошибку ${e.code()}"
        }
        else -> "Нет связи с сервером. Проверьте адрес, Wi-Fi и запуск бэкенда."
    }

    init {
        // Старый открытый токен больше не используется; после обновления нужен вход.
        prefs.edit().remove("access_token").apply()
        restoreSession()
    }
}

