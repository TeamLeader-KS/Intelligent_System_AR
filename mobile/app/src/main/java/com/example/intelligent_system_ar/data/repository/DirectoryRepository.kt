package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.local.Employee
import com.example.intelligent_system_ar.data.model.Workshop
import kotlinx.coroutines.CancellationException

/** Источник справочников (сервер или заглушка). Ошибки сети возвращаются как Result.failure. */
interface DirectoryRepository {
    suspend fun getWorkshops(): Result<List<Workshop>>
    suspend fun getRoles(workshopId: Int): Result<List<String>>
    suspend fun getEmployees(workshopId: Int, role: String): Result<List<Employee>>
}

/** Как runCatching, но не глотает отмену корутины. */
internal suspend fun <T> safeCall(block: suspend () -> T): Result<T> =
    try {
        Result.success(block())
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        Result.failure(e)
    }
