package com.example.intelligent_system_ar.data.local

import com.example.intelligent_system_ar.data.remote.model.ComponentWorkRequest
import com.example.intelligent_system_ar.data.remote.model.DeviceInspectionRequest
import com.google.gson.Gson
import com.google.gson.JsonParseException
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.UUID

/** Private app storage. Entries contain evidence, never passwords or access tokens. */
data class PendingOperation(
    val id: String,
    val equipmentId: Int,
    val inspection: DeviceInspectionRequest? = null,
    val componentId: Int? = null,
    val work: ComponentWorkRequest? = null,
    val inspectionId: Int? = null
)

class InspectionOutbox(root: File, server: String, accountId: Int) {
    private val gson = Gson()
    private val scope = MessageDigest.getInstance("SHA-256")
        .digest("$server\u0000$accountId".toByteArray()).joinToString("") { "%02x".format(it.toInt() and 255) }
    private val directory = File(root, scope)

    fun entries(): List<PendingOperation> {
        val folders=directory.listFiles()
        if(directory.exists() && folders==null) throw IOException("Нет доступа к очереди осмотров")
        return folders.orEmpty().filter { it.isDirectory && !it.name.startsWith(".") }.sortedBy { it.name }.map { folder ->
            try {
                val result = gson.fromJson(File(folder, "operation.json").readText(), PendingOperation::class.java)
                if (result == null || result.id != folder.name) throw IOException("Повреждена запись очереди")
                UUID.fromString(result.id)
                result
            } catch (e: JsonParseException) { throw IOException("Не удалось прочитать очередь осмотров", e) }
            catch (e: IllegalArgumentException) { throw IOException("Повреждён идентификатор очереди", e) }
        }
    }

    fun enqueue(operation: PendingOperation, jpeg: ByteArray? = null) {
        require(UUID.fromString(operation.id).toString() == operation.id)
        if (entries().size >= 20) throw IOException("В очереди 20 записей. Сначала отправьте сохранённые осмотры.")
        if (jpeg != null && jpeg.size > 10 * 1024 * 1024) throw IOException("Снимок превышает 10 МиБ")
        if (!directory.exists() && !directory.mkdirs()) throw IOException("Не удалось создать очередь")
        val temporary = File(directory, ".${operation.id}")
        if (!temporary.mkdir()) throw IOException("Не удалось подготовить запись осмотра")
        try {
            if (jpeg != null) File(temporary, "frame.jpg").writeBytes(jpeg)
            File(temporary, "operation.json").writeText(gson.toJson(operation))
            if (!temporary.renameTo(File(directory, operation.id))) throw IOException("Не удалось сохранить осмотр")
        } finally { temporary.deleteRecursively() }
    }

    fun photo(operation: PendingOperation): File = File(File(directory, operation.id), "frame.jpg")

    fun markCreated(operation: PendingOperation, inspectionId: Int): PendingOperation {
        val updated = operation.copy(inspectionId = inspectionId)
        val folder = File(directory, operation.id)
        val temporary = File(folder, ".operation.tmp")
        temporary.writeText(gson.toJson(updated))
        if (!temporary.renameTo(File(folder, "operation.json"))) throw IOException("Не удалось обновить очередь")
        return updated
    }

    fun remove(operation: PendingOperation) {
        if (!File(directory, operation.id).deleteRecursively()) throw IOException("Не удалось завершить запись очереди")
    }
}
