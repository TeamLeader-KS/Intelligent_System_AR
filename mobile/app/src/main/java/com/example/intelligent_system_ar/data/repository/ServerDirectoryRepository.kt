package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.local.Employee
import com.example.intelligent_system_ar.data.model.Workshop
import com.example.intelligent_system_ar.data.remote.DirectoryApi

/** Цеха, должности и сотрудники с сервера. Токен берётся в момент запроса. */
class ServerDirectoryRepository(
    private val api: () -> DirectoryApi,
    private val token: () -> String?
) : DirectoryRepository {

    private fun bearer(): String =
        "Bearer " + (token() ?: throw IllegalStateException("Нет токена: войдите заново"))

    override suspend fun getWorkshops(): Result<List<Workshop>> = safeCall {
        api().workshops(bearer()).map { Workshop(it.id, it.name) }
    }

    override suspend fun getRoles(workshopId: Int): Result<List<String>> = safeCall {
        api().roles(bearer(), workshopId)
    }

    override suspend fun getEmployees(workshopId: Int, role: String): Result<List<Employee>> = safeCall {
        api().employees(bearer(), workshopId, role).map {
            Employee(it.id, it.fullName, it.role, it.workshopId, it.canRepair)
        }
    }
}
