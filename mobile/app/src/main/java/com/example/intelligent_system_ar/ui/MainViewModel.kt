package com.example.intelligent_system_ar.ui

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.intelligent_system_ar.data.model.UserState
import com.example.intelligent_system_ar.data.auth.TokenStore
import com.example.intelligent_system_ar.data.repository.AuthRepository
import com.example.intelligent_system_ar.data.repository.LoginException
import com.example.intelligent_system_ar.data.remote.ApiClient
import com.example.intelligent_system_ar.data.remote.DirectoryApi
import com.example.intelligent_system_ar.data.remote.ServerConfig
import com.example.intelligent_system_ar.data.remote.model.*
import com.example.intelligent_system_ar.data.local.InspectionOutbox
import com.example.intelligent_system_ar.data.local.PendingOperation
import com.example.intelligent_system_ar.data.ml.CapturedInspection
import com.example.intelligent_system_ar.data.ml.ObjectDetectorHelper
import com.google.gson.JsonParseException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.HttpException
import java.io.IOException
import java.io.File
import java.time.Instant
import java.util.UUID

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("local_server_session", Context.MODE_PRIVATE)
    private val tokenStore = TokenStore(app)
    var serverUrl by mutableStateOf(prefs.getString("server_url", ServerConfig.DEFAULT_URL)!!)
        private set
    private var api = ApiClient.create(serverUrl)

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
    var selectedComponentId by mutableStateOf<Int?>(null)
        private set
    val selectedComponent: ComponentDto? get() = card?.components?.firstOrNull { it.id == selectedComponentId }
    var inspectionComment by mutableStateOf("")
    var visualChecks by mutableStateOf<Set<String>>(emptySet())
    var isSaving by mutableStateOf(false)
        private set
    var saveMessage by mutableStateOf<String?>(null)
        private set
    var pendingCount by mutableStateOf(0)
        private set
    var pendingVisionCount by mutableStateOf(0)
        private set
    var isVisionAnalyzing by mutableStateOf(false)
        private set
    var lastVisionInspection by mutableStateOf<ServerInspectionDto?>(null)
        private set
    var lastVisionImage by mutableStateOf<ByteArray?>(null)
        private set
    var workHistory by mutableStateOf<ComponentWorkHistoryDto?>(null)
        private set
    var isLoadingWork by mutableStateOf(false)
        private set
    var canRecordWork by mutableStateOf(false)
        private set
    var lastInspection by mutableStateOf<SavedInspectionDto?>(null)
        private set
    var reportToShare by mutableStateOf<Pair<File,String>?>(null)
        private set
    var isExporting by mutableStateOf(false)
        private set

    private var sessionJob: Job? = null
    private var equipmentJob: Job? = null
    private var cardJob: Job? = null
    private var historyJob: Job? = null
    private var queueJob: Job? = null
    private var workHistoryJob: Job? = null
    private var exportJob: Job? = null
    private var sessionGeneration = 0

    private fun outbox(): InspectionOutbox = InspectionOutbox(
        File(getApplication<Application>().noBackupFilesDir, "inspection-outbox"), serverUrl, userState.employeeId)

    fun login(address: String, login: String, password: String) {
        if (isLoggingIn) return
        val normalized = try {
            ServerConfig.normalize(address)
        } catch (e: IllegalArgumentException) {
            loginError = e.message
            return
        }
        serverUrl = normalized
        api = ApiClient.create(normalized)
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
                userState = user.toUserState()
                accessToken = token
                canRecordWork = user.role in listOf("ADMIN", "MASTER", "ENGINEER")
                refreshEquipment()
                flushPending(includeVision=false)
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
        sessionGeneration++
        sessionJob?.cancel()
        equipmentJob?.cancel()
        cardJob?.cancel()
        historyJob?.cancel()
        queueJob?.cancel()
        workHistoryJob?.cancel()
        exportJob?.cancel()
        accessToken = null
        tokenStore.clear()
        prefs.edit().remove("access_token").apply()
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
        selectedComponentId = null
        inspectionComment = ""
        visualChecks = emptySet()
        pendingCount = 0
        pendingVisionCount = 0
        isVisionAnalyzing = false
        lastVisionInspection = null
        lastVisionImage = null
        isSaving = false
        canRecordWork = false
        saveMessage = null
        workHistory = null
        lastInspection = null
        reportToShare = null
        isExporting = false
        isLoadingWork = false
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
        val previousEquipmentId = card?.id
        val previousComponentId = selectedComponentId
        card = null
        history = null
        historyError = null
        isLoadingHistory = false
        cardJob = viewModelScope.launch {
            isLoadingCard = true
            cardError = null
            try {
                card = load("Bearer $token")
                selectedComponentId = previousComponentId.takeIf { previousEquipmentId == card?.id && card?.components?.any { it.id == previousComponentId } == true }
                if(previousEquipmentId != card?.id) { visualChecks=emptySet();inspectionComment="";lastInspection=null }
                workHistory = null
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

    fun loadHistory(offset: Int=0) {
        val token = accessToken ?: return
        val id = card?.id ?: return
        historyJob?.cancel()
        historyJob = viewModelScope.launch {
            isLoadingHistory = true
            historyError = null
            try {
                history = api.history("Bearer $token", id,offset=offset.coerceAtLeast(0))
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

    fun consumeReport() { reportToShare=null }
    fun reportShareFailed() { saveMessage="Не удалось открыть окно отправки. Отчёт можно получить в веб-кабинете." }

    fun exportInspection(id: Int,format: String) {
        val token=accessToken ?: return
        if(isExporting || format !in listOf("pdf","xlsx")) return
        val generation=sessionGeneration
        val client=api
        exportJob=viewModelScope.launch {
            isExporting=true
            try {
                val result=withContext(Dispatchers.IO) {
                    val directory=File(getApplication<Application>().cacheDir,"reports")
                    if(!directory.exists() && !directory.mkdirs()) throw IOException("Не удалось создать каталог отчётов")
                    val temporary=File.createTempFile("inspection-",".part",directory)
                    try {
                        client.exportInspection("Bearer $token",id,format).use { body ->
                            body.byteStream().use { source -> temporary.outputStream().use { output ->
                                val buffer=ByteArray(8192)
                                var total=0
                                while(true) {
                                    val n=source.read(buffer)
                                    if(n<0) break
                                    total+=n
                                    if(total>20*1024*1024) throw IOException("Отчёт превышает допустимый размер")
                                    output.write(buffer,0,n)
                                }
                            } }
                        }
                        // A previously shared URI must never start serving a later account's report.
                        val target=File(directory,"inspection-$id-${UUID.randomUUID()}.$format")
                        if(!temporary.renameTo(target)) throw IOException("Не удалось сохранить отчёт")
                        target
                    } finally { temporary.delete() }
                }
                if(generation == sessionGeneration) reportToShare=result to if(format=="pdf") "application/pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            } catch(e: HttpException) { saveMessage=authenticatedError(e) }
            catch(e: IOException) { saveMessage=e.message ?: "Не удалось загрузить отчёт" }
            finally { if(generation == sessionGeneration) isExporting=false }
        }
    }

    fun selectComponent(id: Int) {
        if (card?.components?.any { it.id == id } != true) return
        if(selectedComponentId != id) { visualChecks=emptySet();inspectionComment="";lastInspection=null }
        selectedComponentId = id
        workHistory = null
        loadWorkHistory()
    }

    fun loadWorkHistory(offset: Int=0) {
        val token = accessToken ?: return
        val id = selectedComponentId ?: return
        workHistoryJob?.cancel()
        workHistoryJob = viewModelScope.launch {
            isLoadingWork = true
            try { workHistory = api.workHistory("Bearer $token", id,offset=offset.coerceAtLeast(0)) }
            catch (e: HttpException) { saveMessage = authenticatedError(e) }
            catch (e: IOException) { saveMessage = message(e) }
            catch (e: JsonParseException) { saveMessage = "Не удалось прочитать историю работ" }
            finally { isLoadingWork = false }
        }
    }

    fun saveSnapshot(snapshot: CapturedInspection, equipmentId: Int, componentId: Int, comment: String,checks: Set<String>) {
        if (accessToken == null || isSaving) return
        val generation = sessionGeneration
        val queue = outbox()
        val request = DeviceInspectionRequest(equipmentId, componentId, capturedAt=snapshot.capturedAt,
            modelSha256=ObjectDetectorHelper.MODEL_SHA256, image=InspectionFrame(snapshot.width,snapshot.height),
            defects=snapshot.detections.map { item -> DeviceFindingDto(item.classId,item.confidence,
                listOf(item.box.left,item.box.top,item.box.right,item.box.bottom)) }, comment=comment.trim(),visualChecks=checks.map { ManualVisualCheck(it) })
        queueJob = viewModelScope.launch {
            isSaving = true
            try {
                withContext(Dispatchers.IO) { queue.enqueue(PendingOperation(UUID.randomUUID().toString(),equipmentId,inspection=request),snapshot.jpeg) }
                if (generation != sessionGeneration) return@launch
                saveMessage = "Кадр сохранён на телефоне. Отправка на сервер…"
                sendPending(queue,generation)
            } catch (e: IOException) { saveMessage = e.message ?: "Не удалось сохранить снимок на телефоне" }
            finally { if (generation == sessionGeneration) isSaving=false }
        }
    }

    fun recordWork(action: String, comment: String, hours: Double? = null, cycles: Int? = null) {
        val component = selectedComponent ?: return
        val equipmentId = card?.id ?: return
        if (!canRecordWork || isSaving || accessToken == null) return
        if (comment.isBlank()) { saveMessage="Добавьте комментарий к работе"; return }
        val generation = sessionGeneration
        val queue = outbox()
        queueJob = viewModelScope.launch {
            isSaving = true
            try {
                val pending = withContext(Dispatchers.IO) { queue.entries() }
                if (pending.any { it.work != null }) {
                    saveMessage="Сначала отправьте ранее сохранённые работы, чтобы сохранить порядок наработки"
                    return@launch
                }
                val request=ComponentWorkRequest(action,Instant.now().toString(),component.revision,comment.trim(),hours,cycles)
                withContext(Dispatchers.IO) { queue.enqueue(PendingOperation(UUID.randomUUID().toString(),equipmentId,componentId=component.id,work=request)) }
                sendPending(queue,generation)
            } catch (e: IOException) { saveMessage=e.message ?: "Не удалось сохранить работу на телефоне" }
            finally { if(generation == sessionGeneration) isSaving=false }
        }
    }

    fun saveVisionSnapshot(snapshot: CapturedInspection,equipmentId: Int,componentId: Int?) {
        if(accessToken==null || isSaving) return
        val generation=sessionGeneration
        val queue=outbox()
        val entry=PendingOperation(UUID.randomUUID().toString(),equipmentId,componentId=componentId,
            vision=true,capturedAt=snapshot.capturedAt)
        lastVisionInspection=null
        lastVisionImage=null
        queueJob=viewModelScope.launch {
            isSaving=true
            try {
                withContext(Dispatchers.IO) { queue.enqueue(entry,snapshot.jpeg) }
                if(generation!=sessionGeneration) return@launch
                saveMessage="Кадр сохранён. Анализ одного снимка на локальном сервере…"
                sendPending(queue,generation,includeVision=true,visionId=entry.id)
            } catch(e: IOException) { saveMessage=e.message ?: "Не удалось сохранить кадр для серверного анализа" }
            finally { if(generation==sessionGeneration) {isSaving=false;isVisionAnalyzing=false} }
        }
    }

    fun flushPending(includeVision: Boolean=true) {
        if (accessToken == null || isSaving) return
        val queue=outbox()
        val generation=sessionGeneration
        queueJob=viewModelScope.launch {
            isSaving=true
            try { sendPending(queue,generation,includeVision=includeVision) }
            catch (e: IOException) { saveMessage=e.message ?: "Не удалось прочитать очередь" }
            finally { if(generation == sessionGeneration) {isSaving=false;isVisionAnalyzing=false} }
        }
    }

    fun discardPendingWork() {
        if(accessToken==null || isSaving) return
        val queue=outbox()
        val generation=sessionGeneration
        queueJob=viewModelScope.launch {
            isSaving=true
            try {
                val remaining=withContext(Dispatchers.IO) {
                    queue.entries().filter { it.work!=null }.forEach { queue.remove(it) }
                    queue.entries()
                }
                if(generation==sessionGeneration) {
                    pendingCount=remaining.size
                    pendingVisionCount=remaining.count { it.vision }
                    saveMessage="Локальные запросы работ отменены. Уже принятые сервером записи сохранены. Обновите карточку перед новой работой."
                    card?.id?.let { selectEquipment(it) }
                }
            } catch(e: IOException) { saveMessage=e.message ?: "Не удалось изменить очередь" }
            finally { if(generation==sessionGeneration) isSaving=false }
        }
    }

    private suspend fun sendPending(queue: InspectionOutbox, generation: Int,includeVision: Boolean=false,visionId: String?=null) {
        val token=accessToken ?: return
        val client=api
        val allEntries=withContext(Dispatchers.IO) { queue.entries() }
        pendingCount=allEntries.size
        pendingVisionCount=allEntries.count { it.vision }
        val entries=allEntries.filter { it.canSend(includeVision,visionId) }
        if(entries.isEmpty()) return
        var sendingVision=false
        try {
            for (entry in entries) {
                if (generation != sessionGeneration) return
                sendingVision=entry.vision
                if(entry.vision) {
                    isVisionAnalyzing=true
                    val photo=queue.photo(entry)
                    if(!photo.isFile) throw IOException("Снимок для серверного анализа отсутствует")
                    val visionClient=ApiClient.createVision(serverUrl)
                    val text=MediaType.parse("text/plain")
                    val response=visionClient.analyzeVision("Bearer $token",entry.id,
                        RequestBody.create(text,entry.equipmentId.toString()),RequestBody.create(text,"CAMERA"),
                        entry.componentId?.let { RequestBody.create(text,it.toString()) },
                        entry.capturedAt?.let { RequestBody.create(text,it) },
                        MultipartBody.Part.createFormData("image","frame.jpg",RequestBody.create(MediaType.parse("image/jpeg"),photo)))
                    if(response.analysisLocation!="LOCAL_SERVER" || response.equipmentId!=entry.equipmentId || response.inspectionId<=0)
                        throw JsonParseException("Некорректный контракт серверного ИИ")
                    val jpeg=withContext(Dispatchers.IO) { photo.readBytes() }
                    if(generation!=sessionGeneration) return
                    lastVisionImage=jpeg
                    lastVisionInspection=response
                    isVisionAnalyzing=false
                } else if (entry.inspection != null) {
                    val response=if(entry.inspectionId == null) client.saveInspection("Bearer $token",entry.id,entry.inspection)
                        else client.inspection("Bearer $token",entry.inspectionId)
                    val id=response.inspectionId
                    val saved=if(entry.inspectionId == null) withContext(Dispatchers.IO) { queue.markCreated(entry,id) } else entry
                    val photo=queue.photo(saved)
                    if(!photo.isFile) throw IOException("Снимок очереди отсутствует; запись оставлена для проверки")
                    if (generation != sessionGeneration) return
                    client.attachPhoto("Bearer $token",id,MultipartBody.Part.createFormData("image","frame.jpg",RequestBody.create(MediaType.parse("image/jpeg"),photo)))
                    if(generation == sessionGeneration) lastInspection=response
                } else if (entry.work != null && entry.componentId != null) {
                    client.recordWork("Bearer $token",entry.componentId,entry.id,entry.work)
                } else throw IOException("Неизвестная запись очереди; автоматическая отправка остановлена")
                withContext(Dispatchers.IO) { queue.remove(entry) }
                if (generation != sessionGeneration) return
                pendingCount--
                if(entry.vision) pendingVisionCount--
            }
            saveMessage=if(pendingVisionCount>0) "Записи отправлены. В очереди остались запросы серверного ИИ — они отправляются только по вашему нажатию."
                else "Осмотры и работы сохранены на сервере вместе с фотографиями"
            card?.id?.let { selectEquipment(it) }
        } catch(e: HttpException) {
            saveMessage=when(e.code()) {
                401 -> "Сессия истекла. Очередь сохранена: войдите под тем же пользователем."
                409 -> "Конфликт данных: запись оставлена в очереди. Обновите карточку; повтор не создаёт дубликат."
                422 -> "Сервер отклонил запись: проверьте регистрацию модели и данные осмотра. Запись сохранена в очереди."
                502 -> if(sendingVision) "Локальная модель вернула непонятный ответ. Кадр сохранён для повторного анализа." else "Ошибка ответа сервера. Запись остаётся в очереди."
                503 -> if(sendingVision) "Серверный ИИ недоступен или модель ещё не загружена. Кадр сохранён; быстрый анализ на телефоне работает отдельно." else "Сервер временно недоступен. Запись остаётся в очереди."
                504 -> if(sendingVision) "Серверный ИИ не уложился в таймаут. Кадр и ключ повтора сохранены; повторите отправку вручную." else "Таймаут сервера. Запись остаётся в очереди."
                else -> "${message(e)}. Запись остаётся в очереди."
            }
        } catch(e: IOException) { saveMessage="Нет подтверждения сервера. Запись сохранена на телефоне; нажмите «Отправить очередь»." }
        catch(e: JsonParseException) { saveMessage="Неверный ответ сервера. Запись остаётся в очереди для безопасного повтора." }
        finally { if(generation==sessionGeneration) isVisionAnalyzing=false }
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
            409 -> "Номер неоднозначен или карточка изменилась. Выберите оборудование из списка и обновите карточку."
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
