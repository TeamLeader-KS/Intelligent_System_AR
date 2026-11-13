//package com.example.intelligent_system_ar.data.repository
//
//import com.example.intelligent_system_ar.data.local.Employee
//import com.example.intelligent_system_ar.data.model.Workshop
//import com.example.intelligent_system_ar.data.remote.DirectoryApi
//
///** Реальный сервер (Retrofit). */
//class RemoteDirectoryRepository(private val api: DirectoryApi) : DirectoryRepository {
//
//    override suspend fun getWorkshops(): Result<List<Workshop>> = safeCall {
//        api.getWorkshops().map { Workshop(it.id, it.name) }
//    }
//
//    override suspend fun getRoles(workshopId: Int): Result<List<String>> = safeCall {
//        api.getRoles(workshopId)
//    }
//
//    override suspend fun getEmployees(workshopId: Int, role: String): Result<List<Employee>> = safeCall {
//        api.getEmployees(workshopId, role).map {
//            Employee(it.id, it.name, it.role, it.workshopId, it.canRepair)
//        }
//    }
//}

package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.local.Equipment
import com.example.intelligent_system_ar.data.remote.DirectoryApi

/** Реальный сервер (Retrofit). */
class RemoteDirectoryRepository(private val api: DirectoryApi) {

    // Получение оборудования по токену
    suspend fun getEquipment(token: String): Result<List<Equipment>> = safeCall {
        api.getEquipment("Bearer $token").map { dto ->
            // Преобразуем DTO с сервера в вашу локальную модель Equipment
            Equipment(
                id = dto.id,
                name = dto.name,
                workshopId = dto.workshopId,
                status = "UNKNOWN"
            )
        }
    }
}
