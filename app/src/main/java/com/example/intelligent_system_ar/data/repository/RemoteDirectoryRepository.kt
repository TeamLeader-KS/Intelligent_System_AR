package com.example.intelligent_system_ar.data.repository

import com.example.intelligent_system_ar.data.local.Equipment
import com.example.intelligent_system_ar.data.remote.DirectoryApi

/** Реальный сервер (Retrofit). */
class RemoteDirectoryRepository(private val api: DirectoryApi) {

    // Загрузка списка оборудования текущего цеха
    suspend fun getEquipment(): Result<List<Equipment>> = safeCall {
        // Токен автоматически подставится через AuthInterceptor
        api.getEquipment("").map { dto ->
            Equipment(
                id = dto.id,
                name = dto.name,
                workshopId = dto.workshopId,
                status = dto.status
            )
        }
    }
}